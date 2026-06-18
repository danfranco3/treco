"""Tests for workspace CRUD endpoints."""
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

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


class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_create_valid_git_repo(self, client):
        with patch("app.api.routes.workspaces._validate_git_repo") as mock_val:
            from pathlib import Path
            mock_val.return_value = Path("/tmp/myrepo")
            r = await client.post("/api/workspaces/", json={"name": "my-ws", "repo_path": "/tmp/myrepo"})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "my-ws"
        assert data["repo_path"] == "/tmp/myrepo"

    @pytest.mark.asyncio
    async def test_create_nonexistent_path_returns_400(self, client):
        r = await client.post(
            "/api/workspaces/",
            json={"name": "bad", "repo_path": "/nonexistent/path/xyz"},
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_create_blank_name_returns_422(self, client):
        r = await client.post("/api/workspaces/", json={"name": "  ", "repo_path": "/tmp"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_blank_repo_path_returns_422(self, client):
        r = await client.post("/api/workspaces/", json={"name": "ws", "repo_path": "  "})
        assert r.status_code == 422


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_returns_all_workspaces(self, client, workspace):
        r = await client.get("/api/workspaces/")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["id"] == workspace.id

    @pytest.mark.asyncio
    async def test_empty_when_none_exist(self, client):
        r = await client.get("/api/workspaces/")
        assert r.status_code == 200
        assert r.json() == []


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_returns_workspace(self, client, workspace):
        r = await client.get(f"/api/workspaces/{workspace.id}")
        assert r.status_code == 200
        assert r.json()["id"] == workspace.id

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client):
        r = await client.get(f"/api/workspaces/{uuid.uuid4()}")
        assert r.status_code == 404


class TestPatchWorkspace:
    @pytest.mark.asyncio
    async def test_update_name(self, client, workspace):
        r = await client.patch(f"/api/workspaces/{workspace.id}", json={"name": "new-name"})
        assert r.status_code == 200
        assert r.json()["name"] == "new-name"

    @pytest.mark.asyncio
    async def test_update_repo_path(self, client, workspace):
        with patch("app.api.routes.workspaces._validate_git_repo") as mock_val:
            from pathlib import Path
            mock_val.return_value = Path("/tmp/newrepo")
            r = await client.patch(f"/api/workspaces/{workspace.id}", json={"repo_path": "/tmp/newrepo"})
        assert r.status_code == 200
        assert r.json()["repo_path"] == "/tmp/newrepo"

    @pytest.mark.asyncio
    async def test_blank_name_rejected(self, client, workspace):
        r = await client.patch(f"/api/workspaces/{workspace.id}", json={"name": ""})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_not_found_returns_404(self, client):
        r = await client.patch(f"/api/workspaces/{uuid.uuid4()}", json={"name": "x"})
        assert r.status_code == 404


class TestDeleteWorkspace:
    @pytest.mark.asyncio
    async def test_delete_returns_204(self, client, workspace):
        r = await client.delete(f"/api/workspaces/{workspace.id}")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_deleted_workspace_not_found(self, client, workspace):
        await client.delete(f"/api/workspaces/{workspace.id}")
        r = await client.get(f"/api/workspaces/{workspace.id}")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self, client):
        r = await client.delete(f"/api/workspaces/{uuid.uuid4()}")
        assert r.status_code == 404
