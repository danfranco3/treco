"""Tests for workspace CRUD endpoints."""
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.models.user_workspace import UserWorkspace
from app.models.workspace import Workspace
from tests.shared import TestSessionLocal


@pytest_asyncio.fixture
async def workspace():
    async with TestSessionLocal() as db:
        ws = Workspace(
            id=str(uuid.uuid4()),
            name="test-workspace",
            repo_path="/tmp/repo",
        )
        db.add(ws)
        await db.commit()
        await db.refresh(ws)
        return ws


@pytest_asyncio.fixture
async def workspace_with_owner(workspace, user_with_token):
    """Workspace fixture with the test user as owner member."""
    user, _ = user_with_token
    async with TestSessionLocal() as db:
        db.add(UserWorkspace(user_id=user.id, workspace_id=workspace.id, role="owner"))
        await db.commit()
    return workspace


class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_create_valid_git_repo(self, authed_client):
        client, _ = authed_client
        with patch("app.api.routes.workspaces._validate_git_repo") as mock_val:
            from pathlib import Path
            mock_val.return_value = Path("/tmp/myrepo")
            r = await client.post("/api/workspaces", json={"name": "my-ws", "repo_path": "/tmp/myrepo"})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "my-ws"
        assert data["repo_path"] == "/tmp/myrepo"

    @pytest.mark.asyncio
    async def test_create_nonexistent_path_returns_400(self, authed_client):
        client, _ = authed_client
        r = await client.post(
            "/api/workspaces",
            json={"name": "bad", "repo_path": "/nonexistent/path/xyz"},
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_create_blank_name_returns_422(self, authed_client):
        client, _ = authed_client
        r = await client.post("/api/workspaces", json={"name": "  ", "repo_path": "/tmp"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_blank_repo_path_returns_422(self, authed_client):
        client, _ = authed_client
        r = await client.post("/api/workspaces", json={"name": "ws", "repo_path": "  "})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_unauthenticated_returns_422(self, client):
        with patch("app.api.routes.workspaces._validate_git_repo"):
            r = await client.post("/api/workspaces", json={"name": "ws", "repo_path": "/tmp"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_auto_creates_owner_membership(self, authed_client):
        client, user = authed_client
        with patch("app.api.routes.workspaces._validate_git_repo") as mock_val:
            from pathlib import Path
            mock_val.return_value = Path("/tmp/myrepo")
            r = await client.post("/api/workspaces", json={"name": "new-ws", "repo_path": "/tmp/myrepo"})
        assert r.status_code == 200
        ws_id = r.json()["id"]

        async with TestSessionLocal() as db:
            result = await db.execute(
                __import__("sqlalchemy").select(UserWorkspace).where(
                    UserWorkspace.user_id == user.id,
                    UserWorkspace.workspace_id == ws_id,
                )
            )
            m = result.scalar_one_or_none()
        assert m is not None
        assert m.role == "owner"


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_returns_member_workspaces(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        r = await client.get("/api/workspaces")
        assert r.status_code == 200
        ids = [w["id"] for w in r.json()]
        assert workspace_with_owner.id in ids

    @pytest.mark.asyncio
    async def test_hides_workspaces_user_not_member_of(self, authed_client, workspace):
        client, _ = authed_client
        r = await client.get("/api/workspaces")
        assert r.status_code == 200
        ids = [w["id"] for w in r.json()]
        assert workspace.id not in ids

    @pytest.mark.asyncio
    async def test_empty_when_no_memberships(self, authed_client):
        client, _ = authed_client
        r = await client.get("/api/workspaces")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_422(self, client):
        r = await client.get("/api/workspaces")
        assert r.status_code == 422


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_returns_workspace(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        r = await client.get(f"/api/workspaces/{workspace_with_owner.id}")
        assert r.status_code == 200
        assert r.json()["id"] == workspace_with_owner.id

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, authed_client):
        client, _ = authed_client
        r = await client.get(f"/api/workspaces/{uuid.uuid4()}")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_non_member_returns_403(self, authed_client, workspace):
        client, _ = authed_client
        r = await client.get(f"/api/workspaces/{workspace.id}")
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_422(self, client, workspace):
        r = await client.get(f"/api/workspaces/{workspace.id}")
        assert r.status_code == 422


class TestPatchWorkspace:
    @pytest.mark.asyncio
    async def test_update_name(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        r = await client.patch(f"/api/workspaces/{workspace_with_owner.id}", json={"name": "new-name"})
        assert r.status_code == 200
        assert r.json()["name"] == "new-name"

    @pytest.mark.asyncio
    async def test_update_repo_path(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        with patch("app.api.routes.workspaces._validate_git_repo") as mock_val:
            from pathlib import Path
            mock_val.return_value = Path("/tmp/newrepo")
            r = await client.patch(f"/api/workspaces/{workspace_with_owner.id}", json={"repo_path": "/tmp/newrepo"})
        assert r.status_code == 200
        assert r.json()["repo_path"] == "/tmp/newrepo"

    @pytest.mark.asyncio
    async def test_blank_name_rejected(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        r = await client.patch(f"/api/workspaces/{workspace_with_owner.id}", json={"name": ""})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_not_found_returns_404(self, authed_client):
        client, _ = authed_client
        r = await client.patch(f"/api/workspaces/{uuid.uuid4()}", json={"name": "x"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_non_member_returns_403(self, authed_client, workspace):
        client, _ = authed_client
        r = await client.patch(f"/api/workspaces/{workspace.id}", json={"name": "x"})
        assert r.status_code == 403


class TestDeleteWorkspace:
    @pytest.mark.asyncio
    async def test_delete_returns_204(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        r = await client.delete(f"/api/workspaces/{workspace_with_owner.id}")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_deleted_workspace_not_found(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        await client.delete(f"/api/workspaces/{workspace_with_owner.id}")
        r = await client.get(f"/api/workspaces/{workspace_with_owner.id}")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self, authed_client):
        client, _ = authed_client
        r = await client.delete(f"/api/workspaces/{uuid.uuid4()}")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_non_owner_member_cannot_delete(self, authed_client, workspace, user_with_token):
        client, user = authed_client
        async with TestSessionLocal() as db:
            db.add(UserWorkspace(user_id=user.id, workspace_id=workspace.id, role="member"))
            await db.commit()
        r = await client.delete(f"/api/workspaces/{workspace.id}")
        assert r.status_code == 403


class TestMemberManagement:
    @pytest.mark.asyncio
    async def test_list_members(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        r = await client.get(f"/api/workspaces/{workspace_with_owner.id}/members")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_add_member(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        from app.models.user import User
        async with TestSessionLocal() as db:
            new_user = User(id=str(uuid.uuid4()), github_id="999888", login="new-user")
            db.add(new_user)
            await db.commit()
            new_user_id = new_user.id

        r = await client.post(
            f"/api/workspaces/{workspace_with_owner.id}/members",
            json={"user_id": new_user_id, "role": "member"},
        )
        assert r.status_code == 201
        assert r.json()["role"] == "member"
        assert r.json()["login"] == "new-user"

    @pytest.mark.asyncio
    async def test_add_member_conflict_returns_409(self, authed_client, workspace_with_owner, user_with_token):
        client, user = authed_client
        r = await client.post(
            f"/api/workspaces/{workspace_with_owner.id}/members",
            json={"user_id": user.id, "role": "member"},
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_remove_member(self, authed_client, workspace_with_owner):
        client, _ = authed_client
        from app.models.user import User
        async with TestSessionLocal() as db:
            other = User(id=str(uuid.uuid4()), github_id="777666", login="other-user")
            db.add(other)
            await db.flush()
            db.add(UserWorkspace(user_id=other.id, workspace_id=workspace_with_owner.id, role="member"))
            await db.commit()
            other_id = other.id

        r = await client.delete(f"/api/workspaces/{workspace_with_owner.id}/members/{other_id}")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_owner_cannot_remove_self(self, authed_client, workspace_with_owner, user_with_token):
        client, user = authed_client
        r = await client.delete(f"/api/workspaces/{workspace_with_owner.id}/members/{user.id}")
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_non_owner_cannot_add_member(self, authed_client, workspace, user_with_token):
        client, user = authed_client
        async with TestSessionLocal() as db:
            db.add(UserWorkspace(user_id=user.id, workspace_id=workspace.id, role="member"))
            await db.commit()
        r = await client.post(
            f"/api/workspaces/{workspace.id}/members",
            json={"user_id": str(uuid.uuid4()), "role": "member"},
        )
        assert r.status_code == 403
