"""Tests for tracker integration CRUD endpoints."""
import json

import pytest


@pytest.fixture(autouse=True)
def credential_store(tmp_path, monkeypatch):
    """Point the credential store at a temp file so tests never touch ~/.treco."""
    path = tmp_path / "credentials.json"
    monkeypatch.setattr("app.services.sync.base.CREDENTIALS_FILE", path)
    return path


class TestCreateIntegration:
    @pytest.mark.asyncio
    async def test_create_stores_token_outside_db(self, client, credential_store):
        r = await client.post("/api/integrations", json={
            "workspace_id": "ws1",
            "provider": "jira",
            "config": {"base_url": "https://example.atlassian.net"},
            "token": "super-secret-token",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "jira"
        assert "token" not in body
        assert "credential_ref" not in body
        assert "super-secret-token" not in r.text

        stored = json.loads(credential_store.read_text())
        assert "super-secret-token" in stored.values()

    @pytest.mark.asyncio
    async def test_create_rejects_unknown_provider(self, client):
        r = await client.post("/api/integrations", json={
            "workspace_id": "ws1", "provider": "asana", "token": "t",
        })
        assert r.status_code == 422


class TestListGetIntegration:
    @pytest.mark.asyncio
    async def test_list_filters_by_workspace(self, client):
        for ws in ("ws1", "ws1", "ws2"):
            await client.post("/api/integrations", json={
                "workspace_id": ws, "provider": "linear", "token": "t",
            })
        r = await client.get("/api/integrations", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        assert len(r.json()) == 2

    @pytest.mark.asyncio
    async def test_get_missing_returns_404(self, client):
        r = await client.get("/api/integrations/nope")
        assert r.status_code == 404


class TestUpdateDeleteIntegration:
    @pytest.mark.asyncio
    async def test_patch_toggles_enabled(self, client):
        created = (await client.post("/api/integrations", json={
            "workspace_id": "ws1", "provider": "jira", "token": "t",
        })).json()
        r = await client.patch(f"/api/integrations/{created['id']}", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    @pytest.mark.asyncio
    async def test_delete_removes_row_and_credential(self, client, credential_store):
        created = (await client.post("/api/integrations", json={
            "workspace_id": "ws1", "provider": "jira", "token": "delete-me",
        })).json()
        r = await client.delete(f"/api/integrations/{created['id']}")
        assert r.status_code == 204
        assert (await client.get(f"/api/integrations/{created['id']}")).status_code == 404
        stored = json.loads(credential_store.read_text())
        assert "delete-me" not in stored.values()
