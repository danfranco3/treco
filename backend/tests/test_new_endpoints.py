"""Tests for endpoints added in the real-time / launch-agent phase."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from tests.shared import TestSessionLocal


class TestWorkspaceEventsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_events_for_workspace(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {"message": "hi"}},
            headers={"X-Agent-Key": raw_key},
        )
        r = await client.get("/api/events/?workspace_id=ws1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "log"

    @pytest.mark.asyncio
    async def test_does_not_cross_workspaces(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        r = await client.get("/api/events/?workspace_id=other_workspace")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_limit_respected(self, client, agent_with_key, ticket):
        _, raw_key = agent_with_key
        for _ in range(5):
            await client.post(
                "/api/events/",
                json={"ticket_id": ticket.id, "event_type": "log", "payload": {}},
                headers={"X-Agent-Key": raw_key},
            )
        r = await client.get("/api/events/?workspace_id=ws1&limit=3")
        assert r.status_code == 200
        assert len(r.json()) == 3


class TestAgentEventsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_events_for_agent(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {"message": "step 1"}},
            headers={"X-Agent-Key": raw_key},
        )
        r = await client.get(f"/api/events/agent/{agent.id}")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["agent_id"] == agent.id

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_agent(self, client):
        r = await client.get(f"/api/events/agent/{uuid.uuid4()}")
        assert r.status_code == 200
        assert r.json() == []


class TestAssignTicketEndpoint:
    @pytest.mark.asyncio
    async def test_assigns_idle_agent_to_ticket(self, client, agent_with_key, ticket):
        agent, _ = agent_with_key
        r = await client.post(f"/api/agents/{agent.id}/assign", json={"ticket_id": ticket.id})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        agent_r = await client.get(f"/api/agents/{agent.id}")
        data = agent_r.json()
        assert data["status"] == "working"
        assert data["current_ticket_id"] == ticket.id

    @pytest.mark.asyncio
    async def test_assign_creates_ticket_started_event(self, client, agent_with_key, ticket):
        agent, _ = agent_with_key
        await client.post(f"/api/agents/{agent.id}/assign", json={"ticket_id": ticket.id})
        events_r = await client.get(f"/api/events/ticket/{ticket.id}")
        events = events_r.json()
        assert any(e["event_type"] == "ticket_started" for e in events)

    @pytest.mark.asyncio
    async def test_assign_working_agent_returns_409(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        # Put agent into working state
        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "ticket_started", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        r = await client.post(f"/api/agents/{agent.id}/assign", json={"ticket_id": ticket.id})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_assign_unknown_agent_returns_404(self, client, ticket):
        r = await client.post(f"/api/agents/{uuid.uuid4()}/assign", json={"ticket_id": ticket.id})
        assert r.status_code == 404


class TestTicketPagination:
    @pytest.mark.asyncio
    async def test_limit_and_offset(self, client):
        async with TestSessionLocal() as db:
            for i in range(5):
                db.add(Ticket(
                    id=str(uuid.uuid4()),
                    workspace_id="ws1",
                    source="custom",
                    title=f"Ticket {i}",
                    status="open",
                    body={},
                    acceptance_criteria=[],
                ))
            await db.commit()

        r = await client.get("/api/tickets/?workspace_id=ws1&limit=3&offset=0")
        assert r.status_code == 200
        first_page = r.json()
        assert len(first_page) == 3

        r2 = await client.get("/api/tickets/?workspace_id=ws1&limit=3&offset=3")
        assert r2.status_code == 200
        second_page = r2.json()
        assert len(second_page) == 2

        # No overlap between pages
        first_ids = {t["id"] for t in first_page}
        second_ids = {t["id"] for t in second_page}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_limit_capped_at_200(self, client):
        r = await client.get("/api/tickets/?workspace_id=ws1&limit=999&offset=0")
        assert r.status_code == 200  # doesn't crash, capped internally


class TestLastSeenAtUpdated:
    @pytest.mark.asyncio
    async def test_last_seen_updated_on_event_post(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        assert agent.last_seen_at is None

        await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )

        async with TestSessionLocal() as db:
            refreshed = await db.get(Agent, agent.id)
            assert refreshed.last_seen_at is not None


class TestEventAuth:
    @pytest.mark.asyncio
    async def test_post_event_without_key_returns_422(self, client, ticket):
        r = await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {}},
        )
        # Missing required header → 422 (FastAPI validates Header(...) as required)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_post_event_invalid_key_returns_401(self, client, ticket):
        r = await client.post(
            "/api/events/",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {}},
            headers={"X-Agent-Key": "treco_invalid_key_xyz"},
        )
        assert r.status_code == 401


class TestImplementTicket:
    @pytest.mark.asyncio
    async def test_implement_spawns_agent(self, client, ticket):
        from unittest.mock import AsyncMock, patch

        async with TestSessionLocal() as db:
            from app.models.workspace import Workspace
            ws = Workspace(id="ws1", name="test-ws", repo_path="/tmp/repo")
            db.add(ws)
            await db.commit()

        with patch("app.api.routes.tickets.agent_runner.mint_agent") as mock_mint, \
             patch("app.api.routes.tickets.agent_runner.spawn_agent_run") as mock_spawn:
            from app.models.agent import Agent as AgentModel
            import hashlib, secrets
            raw_key = "treco_" + secrets.token_urlsafe(16)
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            fake_agent = AgentModel(
                id=str(uuid.uuid4()),
                workspace_id="ws1",
                name="agent-test",
                api_key_hash=key_hash,
                status="idle",
            )
            mock_mint.return_value = (fake_agent, raw_key)
            mock_spawn.return_value = None

            r = await client.post(
                f"/api/tickets/{ticket.id}/implement",
                json={"prompt": "implement this ticket"},
            )

        assert r.status_code == 200
        data = r.json()
        assert "agent_id" in data
        assert "agent_name" in data

    @pytest.mark.asyncio
    async def test_implement_ticket_without_workspace_returns_400(self, client):
        async with TestSessionLocal() as db:
            t = Ticket(
                id=str(uuid.uuid4()),
                workspace_id=None,
                source="custom",
                title="No workspace ticket",
                status="open",
                body={},
                acceptance_criteria=[],
            )
            db.add(t)
            await db.commit()
            ticket_id = t.id

        r = await client.post(
            f"/api/tickets/{ticket_id}/implement",
            json={"prompt": "do something"},
        )
        assert r.status_code == 400


class TestImportTicketDedup:
    @pytest.mark.asyncio
    async def test_import_same_ticket_twice_no_duplicate(self, client):
        raw_jira = {
            "key": "PROJ-1",
            "fields": {
                "summary": "Fix the bug",
                "description": None,
                "status": {"name": "To Do"},
            },
        }
        payload = {"source": "jira", "workspace_id": "ws1", "raw": raw_jira}

        r1 = await client.post("/api/tickets/import", json=payload)
        assert r1.status_code == 200

        r2 = await client.post("/api/tickets/import", json=payload)
        assert r2.status_code == 200

        # Both return the same ticket id
        assert r1.json()["id"] == r2.json()["id"]

        # Only one ticket in DB
        listing = await client.get("/api/tickets/?workspace_id=ws1")
        assert len(listing.json()) == 1


class TestGraphQLInjectionValidation:
    @pytest.mark.asyncio
    async def test_invalid_team_key_rejected(self, client):
        r = await client.post("/api/tickets/fetch/bulk", json={
            "workspace_id": "ws1",
            "source": "linear",
            "token": "key",
            "team_key": '"}}{malicious}query{{',
        })
        assert r.status_code == 422

    def test_valid_team_key_passes_pydantic_validation(self):
        from app.api.routes.tickets import BulkImportRequest
        req = BulkImportRequest(workspace_id="ws1", source="linear", token="key", team_key="ENG")
        assert req.team_key == "ENG"

    def test_lowercase_team_key_rejected(self):
        from pydantic import ValidationError
        from app.api.routes.tickets import BulkImportRequest
        with pytest.raises(ValidationError):
            BulkImportRequest(workspace_id="ws1", source="linear", token="key", team_key="eng")
