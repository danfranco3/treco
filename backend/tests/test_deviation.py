"""Deviation service — blocking vs warning semantics, token spikes,
incomplete-criteria flags, and the stuck-agent watchdog pass."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.constants import EventType
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.services.deviation import (
    _check_stuck_agents,
    emit_deviation,
    flag_incomplete_criteria,
    maybe_flag_token_spike,
)
from tests.shared import TestSessionLocal


async def _seed_pair(ticket_status="in_progress", agent_status="working",
                     criteria=None):
    async with TestSessionLocal() as db:
        ticket = Ticket(
            id=str(uuid.uuid4()), workspace_id="ws1", source="custom",
            title="Dev ticket", status=ticket_status, body={},
            acceptance_criteria=criteria or [],
        )
        agent = Agent(
            id=str(uuid.uuid4()), workspace_id="ws1", name=f"dev-{uuid.uuid4().hex[:6]}",
            api_key_hash=uuid.uuid4().hex, status=agent_status,
            current_ticket_id=ticket.id,
        )
        db.add_all([ticket, agent])
        await db.commit()
    return agent, ticket


async def _deviations(ticket_id: str) -> list[AgentEvent]:
    async with TestSessionLocal() as db:
        return list((await db.execute(
            select(AgentEvent).where(
                AgentEvent.ticket_id == ticket_id,
                AgentEvent.event_type == EventType.DEVIATION,
            )
        )).scalars().all())


class TestEmitDeviation:
    @pytest.mark.asyncio
    async def test_blocking_deviation_blocks_agent_and_ticket(self, service_sessions):
        agent, ticket = await _seed_pair()
        await emit_deviation(agent.id, ticket.id, "ws1", "stuck", "no events", block=True)
        async with TestSessionLocal() as db:
            assert (await db.get(Agent, agent.id)).status == "blocked"
            assert (await db.get(Ticket, ticket.id)).status == "blocked"
        events = await _deviations(ticket.id)
        assert events[0].payload["severity"] == "error"
        assert events[0].payload["deviation_type"] == "stuck"

    @pytest.mark.asyncio
    async def test_warning_deviation_records_event_without_blocking(self, service_sessions):
        agent, ticket = await _seed_pair()
        await emit_deviation(agent.id, ticket.id, "ws1", "token_spike", "spike", block=False)
        async with TestSessionLocal() as db:
            assert (await db.get(Agent, agent.id)).status == "working"
            assert (await db.get(Ticket, ticket.id)).status == "in_progress"
        assert (await _deviations(ticket.id))[0].payload["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_blocking_deviation_never_reopens_done_ticket(self, service_sessions):
        agent, ticket = await _seed_pair(ticket_status="done")
        await emit_deviation(agent.id, ticket.id, "ws1", "stuck", "late flag", block=True)
        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).status == "done"


class TestTokenSpike:
    async def _event(self, ticket_id, agent_id, tokens_in=0, tokens_out=0):
        async with TestSessionLocal() as db:
            event = AgentEvent(
                id=str(uuid.uuid4()), agent_id=agent_id, ticket_id=ticket_id,
                workspace_id="ws1", event_type=EventType.LOG,
                tokens_in=tokens_in, tokens_out=tokens_out, payload={},
            )
            db.add(event)
            await db.commit()
        return event

    @pytest.mark.asyncio
    async def test_spike_above_multiplier_flags_warning(self, service_sessions, monkeypatch):
        monkeypatch.setattr(settings, "token_spike_multiplier", 5.0)
        agent, ticket = await _seed_pair()
        for _ in range(3):
            await self._event(ticket.id, agent.id, tokens_in=100)
        spike = await self._event(ticket.id, agent.id, tokens_in=1000)

        await maybe_flag_token_spike(spike)

        events = await _deviations(ticket.id)
        assert len(events) == 1
        assert events[0].payload["deviation_type"] == "token_spike"
        assert events[0].payload["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_normal_usage_not_flagged(self, service_sessions, monkeypatch):
        monkeypatch.setattr(settings, "token_spike_multiplier", 5.0)
        agent, ticket = await _seed_pair()
        for _ in range(3):
            await self._event(ticket.id, agent.id, tokens_in=100)
        normal = await self._event(ticket.id, agent.id, tokens_in=150)

        await maybe_flag_token_spike(normal)
        assert await _deviations(ticket.id) == []

    @pytest.mark.asyncio
    async def test_zero_token_event_ignored(self, service_sessions):
        agent, ticket = await _seed_pair()
        zero = await self._event(ticket.id, agent.id)
        await maybe_flag_token_spike(zero)
        assert await _deviations(ticket.id) == []


class TestIncompleteCriteria:
    @pytest.mark.asyncio
    async def test_unchecked_criteria_flagged_on_finish(self, service_sessions):
        crit = {"id": "c1", "text": "left undone", "done": False}
        agent, ticket = await _seed_pair(criteria=[crit])
        await flag_incomplete_criteria(agent.id, ticket.id, "ws1")
        events = await _deviations(ticket.id)
        assert len(events) == 1
        assert events[0].payload["deviation_type"] == "incomplete_criteria"
        assert events[0].payload["context"]["criterion_ids"] == ["c1"]

    @pytest.mark.asyncio
    async def test_all_done_criteria_not_flagged(self, service_sessions):
        agent, ticket = await _seed_pair(
            criteria=[{"id": "c1", "text": "done", "done": True}]
        )
        await flag_incomplete_criteria(agent.id, ticket.id, "ws1")
        assert await _deviations(ticket.id) == []

    @pytest.mark.asyncio
    async def test_missing_ticket_is_noop(self, service_sessions):
        await flag_incomplete_criteria("agent-x", str(uuid.uuid4()), "ws1")


class TestStuckWatchdog:
    async def _backdate_last_event(self, ticket_id: str, agent_id: str, seconds: int):
        async with TestSessionLocal() as db:
            event = AgentEvent(
                id=str(uuid.uuid4()), agent_id=agent_id, ticket_id=ticket_id,
                workspace_id="ws1", event_type=EventType.LOG, payload={},
                created_at=datetime.utcnow() - timedelta(seconds=seconds),
            )
            db.add(event)
            await db.commit()

    @pytest.mark.asyncio
    async def test_working_agent_with_stale_events_flagged_stuck(
        self, service_sessions, monkeypatch
    ):
        monkeypatch.setattr(settings, "stuck_after_seconds", 60)
        agent, ticket = await _seed_pair()
        await self._backdate_last_event(ticket.id, agent.id, seconds=300)

        await _check_stuck_agents()

        events = await _deviations(ticket.id)
        assert any(e.payload["deviation_type"] == "stuck" for e in events)
        async with TestSessionLocal() as db:
            assert (await db.get(Agent, agent.id)).status == "blocked"

    @pytest.mark.asyncio
    async def test_recently_active_agent_not_flagged(self, service_sessions, monkeypatch):
        monkeypatch.setattr(settings, "stuck_after_seconds", 600)
        agent, ticket = await _seed_pair()
        await self._backdate_last_event(ticket.id, agent.id, seconds=5)

        await _check_stuck_agents()
        assert await _deviations(ticket.id) == []

    @pytest.mark.asyncio
    async def test_agent_with_no_events_not_flagged(self, service_sessions, monkeypatch):
        """An agent that just started (no events yet) must not be reaped."""
        monkeypatch.setattr(settings, "stuck_after_seconds", 60)
        agent, ticket = await _seed_pair()
        await _check_stuck_agents()
        assert await _deviations(ticket.id) == []
