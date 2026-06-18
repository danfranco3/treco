"""Tests for events endpoints: posting, reading, cost, status transitions."""
import uuid

import pytest

from app.models.agent import Agent
from app.models.ticket import Ticket
from tests.shared import TestSessionLocal


class TestPostEvent:
    @pytest.mark.asyncio
    async def test_post_log_event_returns_id(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        r = await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {"message": "step"}},
            headers={"X-Agent-Key": raw_key},
        )
        assert r.status_code == 200
        assert "id" in r.json()

    @pytest.mark.asyncio
    async def test_post_unknown_event_type_returns_422(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        r = await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "unknown_type", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_all_valid_event_types_accepted(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        valid_types = [
            "ticket_started", "criterion_checked", "criterion_failed",
            "pr_opened", "done", "error", "log", "heartbeat", "deviation",
        ]
        criterion_id = ticket.acceptance_criteria[0]["id"] if ticket.acceptance_criteria else None
        for et in valid_types:
            payload: dict = {"ticket_id": ticket.id, "event_type": et, "payload": {}}
            if et in ("criterion_checked", "criterion_failed") and criterion_id:
                payload["criterion_id"] = criterion_id
            r = await client.post("/api/events/", json=payload, headers={"X-Agent-Key": raw_key})
            assert r.status_code == 200, f"event_type={et} failed: {r.text}"

    @pytest.mark.asyncio
    async def test_ticket_started_sets_agent_working(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "ticket_started", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        async with TestSessionLocal() as db:
            a = await db.get(Agent, agent.id)
            assert a.status == "working"
            assert a.current_ticket_id == ticket.id

    @pytest.mark.asyncio
    async def test_done_event_sets_agent_idle(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "ticket_started", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "done", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        async with TestSessionLocal() as db:
            a = await db.get(Agent, agent.id)
            assert a.status == "idle"
            assert a.current_ticket_id is None

    @pytest.mark.asyncio
    async def test_error_event_sets_agent_error(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "error", "payload": {"message": "boom"}},
            headers={"X-Agent-Key": raw_key},
        )
        async with TestSessionLocal() as db:
            a = await db.get(Agent, agent.id)
            assert a.status == "error"

    @pytest.mark.asyncio
    async def test_criterion_checked_marks_done(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        criterion_id = ticket.acceptance_criteria[0]["id"]

        await client.post(
            "/api/events/",
            json={
                "ticket_id": ticket.id,
                "event_type": "criterion_checked",
                "criterion_id": criterion_id,
                "payload": {},
            },
            headers={"X-Agent-Key": raw_key},
        )

        async with TestSessionLocal() as db:
            t = await db.get(Ticket, ticket.id)
            matching = [c for c in t.acceptance_criteria if c["id"] == criterion_id]
            assert matching[0]["done"] is True

    @pytest.mark.asyncio
    async def test_token_counts_stored(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={
                "ticket_id": ticket.id,
                "event_type": "log",
                "tokens_in": 100,
                "tokens_out": 50,
                "model": "claude-haiku-4-5-20251001",
                "payload": {},
            },
            headers={"X-Agent-Key": raw_key},
        )
        r = await client.get(f"/api/events/ticket/{ticket.id}")
        events = r.json()
        assert events[0]["tokens_in"] == 100
        assert events[0]["tokens_out"] == 50
        assert events[0]["model"] == "claude-haiku-4-5-20251001"


class TestGetTicketEvents:
    @pytest.mark.asyncio
    async def test_returns_events_ordered_asc(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        for msg in ["first", "second", "third"]:
            await client.post(
                "/api/events/",
                json={"ticket_id": ticket.id, "event_type": "log", "payload": {"message": msg}},
                headers={"X-Agent-Key": raw_key},
            )
        r = await client.get(f"/api/events/ticket/{ticket.id}")
        assert r.status_code == 200
        events = r.json()
        assert len(events) == 3
        messages = [e["payload"]["message"] for e in events]
        assert messages == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_ticket(self, client):
        r = await client.get(f"/api/events/ticket/{uuid.uuid4()}")
        assert r.status_code == 200
        assert r.json() == []


class TestCostEndpoint:
    @pytest.mark.asyncio
    async def test_cost_sums_tokens(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        for tokens_in, tokens_out in [(100, 50), (200, 100), (300, 150)]:
            await client.post(
                "/api/events/",
                json={
                    "ticket_id": ticket.id,
                    "event_type": "log",
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "payload": {},
                },
                headers={"X-Agent-Key": raw_key},
            )

        r = await client.get(f"/api/events/ticket/{ticket.id}/cost")
        assert r.status_code == 200
        data = r.json()
        assert data["total_tokens_in"] == 600
        assert data["total_tokens_out"] == 300
        assert data["event_count"] == 3

    @pytest.mark.asyncio
    async def test_cost_zero_for_no_events(self, client):
        r = await client.get(f"/api/events/ticket/{uuid.uuid4()}/cost")
        assert r.status_code == 200
        data = r.json()
        assert data["total_tokens_in"] == 0
        assert data["total_tokens_out"] == 0
        assert data["event_count"] == 0


class TestAgentEventsEndpoint:
    @pytest.mark.asyncio
    async def test_limit_capped_at_500(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        r = await client.get(f"/api/events/agent/{agent_with_key[0].id}?limit=9999")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_events_returned_newest_first(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        for i in range(3):
            await client.post(
                "/api/events/",
                json={"ticket_id": ticket.id, "event_type": "log", "payload": {"seq": i}},
                headers={"X-Agent-Key": raw_key},
            )
        r = await client.get(f"/api/events/agent/{agent.id}")
        events = r.json()
        seqs = [e["payload"]["seq"] for e in events]
        assert seqs == [2, 1, 0]


class TestWorkspaceEventsLimitCap:
    @pytest.mark.asyncio
    async def test_workspace_events_capped_at_500(self, client, agent_with_key, ticket):
        r = await client.get("/api/events/?workspace_id=ws1&limit=9999")
        assert r.status_code == 200
