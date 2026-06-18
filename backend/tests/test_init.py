"""Tests for the /api/init bootstrap endpoint."""
import pytest

from app.models.agent import Agent
from app.models.workspace import Workspace
from tests.shared import TestSessionLocal


class TestInitEndpoint:
    @pytest.mark.asyncio
    async def test_init_creates_agent_and_workspace(self, client):
        r = await client.post("/api/init/", json={"workspace_id": "new-ws", "agent_name": "bot-1"})
        assert r.status_code == 200
        data = r.json()
        assert "api_key" in data
        assert "agent_id" in data
        assert data["workspace_id"] == "new-ws"

    @pytest.mark.asyncio
    async def test_api_key_starts_with_prefix(self, client):
        r = await client.post("/api/init/", json={"workspace_id": "ws-prefix", "agent_name": "bot"})
        assert r.json()["api_key"].startswith("treco_")

    @pytest.mark.asyncio
    async def test_workspace_auto_created_if_missing(self, client):
        r = await client.post("/api/init/", json={"workspace_id": "auto-ws", "agent_name": "auto-bot"})
        assert r.status_code == 200

        async with TestSessionLocal() as db:
            ws = await db.get(Workspace, "auto-ws")
            assert ws is not None
            assert ws.id == "auto-ws"

    @pytest.mark.asyncio
    async def test_existing_workspace_not_duplicated(self, client):
        async with TestSessionLocal() as db:
            db.add(Workspace(id="exist-ws", name="exist-ws", repo_path=None))
            await db.commit()

        r = await client.post("/api/init/", json={"workspace_id": "exist-ws", "agent_name": "new-bot"})
        assert r.status_code == 200

        async with TestSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Workspace).where(Workspace.id == "exist-ws")
            )
            ws_list = result.scalars().all()
            assert len(ws_list) == 1

    @pytest.mark.asyncio
    async def test_duplicate_agent_name_returns_409(self, client):
        await client.post("/api/init/", json={"workspace_id": "dup-ws", "agent_name": "dup-bot"})
        r = await client.post("/api/init/", json={"workspace_id": "dup-ws", "agent_name": "dup-bot"})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_same_name_different_workspace_allowed(self, client):
        await client.post("/api/init/", json={"workspace_id": "ws-a", "agent_name": "shared-name"})
        r = await client.post("/api/init/", json={"workspace_id": "ws-b", "agent_name": "shared-name"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_agent_name_returns_422(self, client):
        r = await client.post("/api/init/", json={"workspace_id": "ws1"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_workspace_id_returns_422(self, client):
        r = await client.post("/api/init/", json={"agent_name": "bot"})
        assert r.status_code == 422
