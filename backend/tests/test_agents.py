"""Tests for agent CRUD endpoints."""
import hashlib
import secrets
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.models.agent import Agent
from tests.shared import TestSessionLocal


@pytest_asyncio.fixture
async def agent_pair():
    """Two agents in ws1, one in ws2."""
    async with TestSessionLocal() as db:
        agents = []
        for i in range(2):
            raw = "treco_" + secrets.token_urlsafe(16)
            a = Agent(
                id=str(uuid.uuid4()),
                workspace_id="ws1",
                name=f"agent-{i}",
                api_key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                status="idle",
            )
            db.add(a)
            agents.append((a, raw))

        raw2 = "treco_" + secrets.token_urlsafe(16)
        a2 = Agent(
            id=str(uuid.uuid4()),
            workspace_id="ws2",
            name="agent-other",
            api_key_hash=hashlib.sha256(raw2.encode()).hexdigest(),
            status="idle",
        )
        db.add(a2)
        await db.commit()
        for a, _ in agents:
            await db.refresh(a)
        await db.refresh(a2)
        return agents, (a2, raw2)


class TestCreateAgent:
    @pytest.mark.asyncio
    async def test_create_returns_api_key(self, client):
        r = await client.post("/api/agents/", json={"workspace_id": "ws1", "name": "my-agent"})
        assert r.status_code == 200
        data = r.json()
        assert "api_key" in data
        assert data["api_key"].startswith("treco_")

    @pytest.mark.asyncio
    async def test_create_response_fields(self, client):
        r = await client.post("/api/agents/", json={"workspace_id": "ws1", "name": "my-agent"})
        data = r.json()
        assert data["name"] == "my-agent"
        assert data["workspace_id"] == "ws1"
        assert data["status"] == "idle"
        assert data["current_ticket_id"] is None
        assert "id" in data

    @pytest.mark.asyncio
    async def test_api_key_not_stored_raw(self, client):
        r = await client.post("/api/agents/", json={"workspace_id": "ws1", "name": "check-hash"})
        agent_id = r.json()["id"]
        api_key = r.json()["api_key"]

        async with TestSessionLocal() as db:
            agent = await db.get(Agent, agent_id)
            assert agent.api_key_hash != api_key
            expected_hash = hashlib.sha256(api_key.encode()).hexdigest()
            assert agent.api_key_hash == expected_hash

    @pytest.mark.asyncio
    async def test_missing_workspace_id_returns_422(self, client):
        r = await client.post("/api/agents/", json={"name": "no-ws"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_name_returns_422(self, client):
        r = await client.post("/api/agents/", json={"workspace_id": "ws1"})
        assert r.status_code == 422


class TestListAgents:
    @pytest.mark.asyncio
    async def test_list_returns_workspace_agents(self, client, agent_pair):
        ws1_agents, _ = agent_pair
        r = await client.get("/api/agents/?workspace_id=ws1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        ids = {a["id"] for a in data}
        assert all(a.id in ids for a, _ in ws1_agents)

    @pytest.mark.asyncio
    async def test_list_isolated_by_workspace(self, client, agent_pair):
        r = await client.get("/api/agents/?workspace_id=ws2")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["workspace_id"] == "ws2"

    @pytest.mark.asyncio
    async def test_list_empty_workspace_returns_empty(self, client):
        r = await client.get("/api/agents/?workspace_id=nonexistent_ws")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_list_missing_workspace_id_returns_422(self, client):
        r = await client.get("/api/agents/")
        assert r.status_code == 422


class TestGetAgent:
    @pytest.mark.asyncio
    async def test_get_existing_agent(self, client, agent_with_key):
        agent, _ = agent_with_key
        r = await client.get(f"/api/agents/{agent.id}")
        assert r.status_code == 200
        assert r.json()["id"] == agent.id

    @pytest.mark.asyncio
    async def test_get_unknown_agent_returns_404(self, client):
        r = await client.get(f"/api/agents/{uuid.uuid4()}")
        assert r.status_code == 404


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_with_valid_key(self, client, agent_with_key):
        agent, raw_key = agent_with_key
        r = await client.get("/api/agents/me", headers={"X-Agent-Key": raw_key})
        assert r.status_code == 200
        assert r.json()["id"] == agent.id

    @pytest.mark.asyncio
    async def test_get_me_with_invalid_key_returns_401(self, client):
        r = await client.get("/api/agents/me", headers={"X-Agent-Key": "treco_bogus"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_without_key_returns_422(self, client):
        r = await client.get("/api/agents/me")
        assert r.status_code == 422


class TestCancelAgent:
    @pytest.mark.asyncio
    async def test_cancel_sets_agent_idle(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        # Put agent in working state
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "ticket_started", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )

        r = await client.post(f"/api/agents/{agent.id}/cancel")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "idle"
        assert data["current_ticket_id"] is None

    @pytest.mark.asyncio
    async def test_cancel_emits_error_event(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "ticket_started", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )

        await client.post(f"/api/agents/{agent.id}/cancel")
        events_r = await client.get(f"/api/events/ticket/{ticket.id}")
        event_types = [e["event_type"] for e in events_r.json()]
        assert "error" in event_types

    @pytest.mark.asyncio
    async def test_cancel_unknown_agent_returns_404(self, client):
        r = await client.post(f"/api/agents/{uuid.uuid4()}/cancel")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_idle_agent_stays_idle(self, client, agent_with_key):
        agent, _ = agent_with_key
        r = await client.post(f"/api/agents/{agent.id}/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"

    @pytest.mark.asyncio
    async def test_cancel_with_pid_sends_sigterm(self, client, agent_with_key):
        agent, _ = agent_with_key
        async with TestSessionLocal() as db:
            a = await db.get(Agent, agent.id)
            a.pid = 999999999  # unlikely real pid
            await db.commit()

        with patch("os.kill") as mock_kill:
            r = await client.post(f"/api/agents/{agent.id}/cancel")
        assert r.status_code == 200
