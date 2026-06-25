"""Shared test fixtures for backend tests."""
import hashlib
import secrets
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, get_db
from app.main import app
from app.models.agent import Agent
from app.models.ticket import Ticket
from tests.shared import TestSessionLocal, engine



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
async def local_client():
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def remote_client():
    transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
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
