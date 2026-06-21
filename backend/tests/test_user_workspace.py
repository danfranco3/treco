"""Tests for UserWorkspace membership model and agent route enforcement."""
import hashlib
import secrets
import uuid

import pytest
import pytest_asyncio

from app.models.agent import Agent
from app.models.user import User
from app.models.user_workspace import UserWorkspace
from app.models.workspace import Workspace
from app.services.auth import check_workspace_member, create_jwt
from tests.shared import TestSessionLocal


async def _create_workspace_with_owner() -> tuple[Workspace, User, str]:
    """Returns (workspace, user, jwt_token)."""
    async with TestSessionLocal() as db:
        user = User(id=str(uuid.uuid4()), github_id=str(secrets.randbelow(10**9)), login="owner-user")
        ws = Workspace(id=str(uuid.uuid4()), name="test-ws", repo_path="/tmp")
        db.add(user)
        db.add(ws)
        await db.flush()
        db.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))
        await db.commit()
        await db.refresh(user)
        await db.refresh(ws)
    token = create_jwt(user.id)
    return ws, user, token


class TestUserWorkspaceModel:
    @pytest.mark.asyncio
    async def test_create_owner_membership(self):
        async with TestSessionLocal() as db:
            user = User(id=str(uuid.uuid4()), github_id="111", login="u1")
            ws = Workspace(id=str(uuid.uuid4()), name="ws", repo_path=None)
            db.add(user)
            db.add(ws)
            await db.flush()
            m = UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner")
            db.add(m)
            await db.commit()

            from sqlalchemy import select
            result = await db.execute(
                select(UserWorkspace).where(
                    UserWorkspace.user_id == user.id,
                    UserWorkspace.workspace_id == ws.id,
                )
            )
            saved = result.scalar_one()
            assert saved.role == "owner"

    @pytest.mark.asyncio
    async def test_composite_primary_key_enforced(self):
        from sqlalchemy.exc import IntegrityError
        async with TestSessionLocal() as db:
            user = User(id=str(uuid.uuid4()), github_id="222", login="u2")
            ws = Workspace(id=str(uuid.uuid4()), name="ws", repo_path=None)
            db.add(user)
            db.add(ws)
            await db.flush()
            db.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))
            await db.commit()

        with pytest.raises(IntegrityError):
            async with TestSessionLocal() as db:
                db.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="member"))
                await db.commit()


class TestCheckWorkspaceMember:
    @pytest.mark.asyncio
    async def test_returns_membership_for_valid_member(self):
        ws, user, _ = await _create_workspace_with_owner()
        async with TestSessionLocal() as db:
            m = await check_workspace_member(user.id, ws.id, db)
        assert m.role == "owner"
        assert m.user_id == user.id

    @pytest.mark.asyncio
    async def test_raises_403_for_non_member(self):
        from fastapi import HTTPException
        ws, _, _ = await _create_workspace_with_owner()
        stranger_id = str(uuid.uuid4())
        async with TestSessionLocal() as db:
            with pytest.raises(HTTPException) as exc_info:
                await check_workspace_member(stranger_id, ws.id, db)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_raises_403_for_nonexistent_workspace(self):
        from fastapi import HTTPException
        _, user, _ = await _create_workspace_with_owner()
        async with TestSessionLocal() as db:
            with pytest.raises(HTTPException) as exc_info:
                await check_workspace_member(user.id, str(uuid.uuid4()), db)
        assert exc_info.value.status_code == 403


class TestAgentRoutesEnforcement:
    @pytest_asyncio.fixture
    async def setup(self, client):
        ws, user, token = await _create_workspace_with_owner()
        return client, ws, user, token

    @pytest.mark.asyncio
    async def test_create_agent_without_auth_returns_422(self, setup):
        client, ws, _, _ = setup
        r = await client.post("/api/agents", json={"workspace_id": ws.id, "name": "a"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_agent_non_member_returns_403(self, setup):
        client, ws, _, _ = setup
        stranger = User(id=str(uuid.uuid4()), github_id="strangerid", login="stranger")
        async with TestSessionLocal() as db:
            db.add(stranger)
            await db.commit()
        stranger_token = create_jwt(stranger.id)
        r = await client.post(
            "/api/agents",
            json={"workspace_id": ws.id, "name": "a"},
            headers={"Authorization": f"Bearer {stranger_token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_create_agent_member_succeeds(self, setup):
        client, ws, _, token = setup
        r = await client.post(
            "/api/agents",
            json={"workspace_id": ws.id, "name": "my-agent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["workspace_id"] == ws.id
        assert "api_key" in r.json()

    @pytest.mark.asyncio
    async def test_list_agents_without_auth_returns_422(self, setup):
        client, ws, _, _ = setup
        r = await client.get(f"/api/agents?workspace_id={ws.id}")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_list_agents_non_member_returns_403(self, setup):
        client, ws, _, _ = setup
        async with TestSessionLocal() as db:
            stranger = User(id=str(uuid.uuid4()), github_id="stranger99", login="stranger")
            db.add(stranger)
            await db.commit()
        stranger_token = create_jwt(stranger.id)
        r = await client.get(
            f"/api/agents?workspace_id={ws.id}",
            headers={"Authorization": f"Bearer {stranger_token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_list_agents_member_succeeds(self, setup):
        client, ws, _, token = setup
        r = await client.get(
            f"/api/agents?workspace_id={ws.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)
