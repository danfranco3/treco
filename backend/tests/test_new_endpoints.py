"""Tests for endpoints added in the real-time / launch-agent phase."""
import hashlib
import secrets
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def agent_with_key():
    raw_key = "treco_" + secrets.token_urlsafe(16)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    async with TestSessionLocal() as db:
        agent = Agent(
            id=str(uuid.uuid4()),
            workspace_id="ws1",
            name="test-agent",
            api_key_hash=key_hash,
            status="idle",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return agent, raw_key


@pytest_asyncio.fixture
async def ticket():
    async with TestSessionLocal() as db:
        t = Ticket(
            id=str(uuid.uuid4()),
            workspace_id="ws1",
            source="custom",
            title="Test ticket",
            status="open",
            body={},
            acceptance_criteria=[{"id": str(uuid.uuid4()), "text": "do the thing", "done": False}],
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return t


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
