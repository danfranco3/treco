"""Tests for deviation detection logic."""
import uuid

import pytest
import pytest_asyncio

from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.services.deviation_detector import check_post_event
from tests.shared import TestSessionLocal


def _make_agent(workspace_id: str = "ws1") -> Agent:
    return Agent(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name="test-agent",
        api_key_hash="hash",
        status="working",
    )


def _make_ticket(criteria: list[dict]) -> Ticket:
    return Ticket(
        id=str(uuid.uuid4()),
        workspace_id="ws1",
        source="custom",
        title="Test ticket",
        status="open",
        body={},
        acceptance_criteria=criteria,
    )


def _make_event(agent: Agent, ticket: Ticket, event_type: str, tokens_in: int = 0, tokens_out: int = 0) -> AgentEvent:
    return AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=ticket.id,
        workspace_id=agent.workspace_id,
        event_type=event_type,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        payload={},
    )


class TestIncompleteDeviations:
    @pytest.mark.asyncio
    async def test_done_with_unchecked_criteria_emits_deviation(self):
        agent = _make_agent()
        ticket = _make_ticket([
            {"id": str(uuid.uuid4()), "text": "do thing A", "done": True},
            {"id": str(uuid.uuid4()), "text": "do thing B", "done": False},
        ])
        event = _make_event(agent, ticket, "done")

        async with TestSessionLocal() as db:
            db.add(agent)
            db.add(ticket)
            db.add(event)
            await db.commit()

            deviations = await check_post_event(event, agent, db)

        assert len(deviations) == 1
        assert deviations[0].payload["deviation_type"] == "incomplete_criteria"
        assert deviations[0].payload["severity"] == "error"

    @pytest.mark.asyncio
    async def test_done_with_all_criteria_checked_no_deviation(self):
        agent = _make_agent()
        ticket = _make_ticket([
            {"id": str(uuid.uuid4()), "text": "do thing A", "done": True},
            {"id": str(uuid.uuid4()), "text": "do thing B", "done": True},
        ])
        event = _make_event(agent, ticket, "done")

        async with TestSessionLocal() as db:
            db.add(agent)
            db.add(ticket)
            db.add(event)
            await db.commit()

            deviations = await check_post_event(event, agent, db)

        assert not any(d.payload["deviation_type"] == "incomplete_criteria" for d in deviations)

    @pytest.mark.asyncio
    async def test_done_with_no_criteria_no_deviation(self):
        agent = _make_agent()
        ticket = _make_ticket([])
        event = _make_event(agent, ticket, "done")

        async with TestSessionLocal() as db:
            db.add(agent)
            db.add(ticket)
            db.add(event)
            await db.commit()

            deviations = await check_post_event(event, agent, db)

        assert deviations == []


class TestTokenSpikeDeviations:
    @pytest.mark.asyncio
    async def test_token_spike_with_enough_prior_points_emits_deviation(self):
        agent = _make_agent()
        ticket = _make_ticket([])

        async with TestSessionLocal() as db:
            db.add(agent)
            db.add(ticket)
            for _ in range(5):
                db.add(_make_event(agent, ticket, "log", tokens_in=50, tokens_out=50))
            await db.commit()

            spike = _make_event(agent, ticket, "log", tokens_in=500, tokens_out=500)
            db.add(spike)
            await db.commit()

            deviations = await check_post_event(spike, agent, db)

        assert any(d.payload["deviation_type"] == "token_spike" for d in deviations)

    @pytest.mark.asyncio
    async def test_token_spike_needs_5_prior_points(self):
        agent = _make_agent()
        ticket = _make_ticket([])

        async with TestSessionLocal() as db:
            db.add(agent)
            db.add(ticket)
            for _ in range(3):
                db.add(_make_event(agent, ticket, "log", tokens_in=50, tokens_out=50))
            await db.commit()

            spike = _make_event(agent, ticket, "log", tokens_in=5000, tokens_out=5000)
            db.add(spike)
            await db.commit()

            deviations = await check_post_event(spike, agent, db)

        assert not any(d.payload["deviation_type"] == "token_spike" for d in deviations)

    @pytest.mark.asyncio
    async def test_normal_token_usage_no_spike(self):
        agent = _make_agent()
        ticket = _make_ticket([])

        async with TestSessionLocal() as db:
            db.add(agent)
            db.add(ticket)
            for _ in range(5):
                db.add(_make_event(agent, ticket, "log", tokens_in=50, tokens_out=50))
            await db.commit()

            normal = _make_event(agent, ticket, "log", tokens_in=100, tokens_out=100)
            db.add(normal)
            await db.commit()

            deviations = await check_post_event(normal, agent, db)

        assert not any(d.payload["deviation_type"] == "token_spike" for d in deviations)
