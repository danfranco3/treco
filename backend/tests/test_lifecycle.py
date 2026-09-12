"""Tests for ticket lifecycle transitions, tier gates, pause/resume, and meta."""
import pytest

from app.core.config import settings
from app.models.agent import Agent
from app.models.ticket import Ticket
from tests.shared import TestSessionLocal


class TestEventTransitions:
    @pytest.mark.asyncio
    async def test_deviation_blocks_ticket_and_agent(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        r = await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "deviation",
                  "payload": {"deviation_type": "stuck"}},
            headers={"X-Agent-Key": raw_key},
        )
        assert r.status_code == 200
        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).status == "blocked"
            assert (await db.get(Agent, agent.id)).status == "blocked"

    @pytest.mark.asyncio
    async def test_permission_requested_moves_ticket_to_hitl_review(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        r = await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "permission_requested",
                  "payload": {"prompt": "rm -rf build?"}},
            headers={"X-Agent-Key": raw_key},
        )
        assert r.status_code == 200
        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).status == "hitl_review"

    @pytest.mark.asyncio
    async def test_error_event_blocks_ticket(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        r = await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "error", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        assert r.status_code == 200
        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).status == "blocked"


class TestImplementGates:
    @pytest.mark.asyncio
    async def test_cloud_offload_returns_402_on_free_tier(self, client, ticket, monkeypatch):
        monkeypatch.setattr(settings, "tier", "free")
        r = await client.post(f"/api/tickets/{ticket.id}/implement", json={
            "method": "anthropic", "execution_mode": "cloud",
        })
        assert r.status_code == 402

    @pytest.mark.asyncio
    async def test_cloud_offload_on_pro_tier_is_not_payment_gated(self, client, ticket, monkeypatch):
        monkeypatch.setattr(settings, "tier", "pro")
        r = await client.post(f"/api/tickets/{ticket.id}/implement", json={
            "method": "anthropic", "execution_mode": "cloud",
        })
        assert r.status_code == 501

    @pytest.mark.asyncio
    async def test_concurrency_limit_returns_409(self, client, ticket, agent_with_key, monkeypatch):
        monkeypatch.setattr(settings, "max_parallel_agents", 1)
        agent, _ = agent_with_key
        async with TestSessionLocal() as db:
            working = await db.get(Agent, agent.id)
            working.status = "working"
            db.add(working)
            await db.commit()
        r = await client.post(f"/api/tickets/{ticket.id}/implement", json={
            "method": "anthropic",
        })
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_implement_missing_ticket_returns_404(self, client):
        r = await client.post("/api/tickets/nope/implement", json={"method": "anthropic"})
        assert r.status_code == 404


class TestPauseResume:
    @pytest.mark.asyncio
    async def test_pause_requires_working_agent(self, client, agent_with_key):
        agent, _ = agent_with_key
        r = await client.post(f"/api/agents/{agent.id}/pause")
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_pause_then_resume(self, client, agent_with_key):
        agent, _ = agent_with_key
        async with TestSessionLocal() as db:
            a = await db.get(Agent, agent.id)
            a.status = "working"
            db.add(a)
            await db.commit()
        assert (await client.post(f"/api/agents/{agent.id}/pause")).status_code == 200
        assert (await client.post(f"/api/agents/{agent.id}/resume")).status_code == 200
        assert (await client.post(f"/api/agents/{agent.id}/resume")).status_code == 409

    @pytest.mark.asyncio
    async def test_pause_missing_agent_returns_404(self, client):
        r = await client.post("/api/agents/nope/pause")
        assert r.status_code == 404


class TestMetaTier:
    @pytest.mark.asyncio
    async def test_tier_endpoint_reflects_settings(self, client, monkeypatch):
        monkeypatch.setattr(settings, "tier", "pro")
        monkeypatch.setattr(settings, "max_parallel_agents", 3)
        r = await client.get("/api/meta/tier")
        assert r.status_code == 200
        assert r.json() == {"tier": "pro", "max_parallel_agents": 3}
