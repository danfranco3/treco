"""Tests for the tool registry endpoints."""
import hashlib
import json

import pytest

SAFE_DEFINITION = {
    "description": "count words",
    "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
    "entrypoint": "count_words",
}


def _checksum(definition: dict) -> str:
    return hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()


class TestCreateTool:
    @pytest.mark.asyncio
    async def test_create_local_tool(self, client):
        r = await client.post("/api/tools", json={
            "workspace_id": "ws1", "name": "wordcount", "kind": "python",
            "definition": SAFE_DEFINITION,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "local"
        assert body["safety_flag"] == "unverified"
        assert body["checksum"] == _checksum(SAFE_DEFINITION)

    @pytest.mark.asyncio
    async def test_network_definition_flagged_high_risk(self, client):
        definition = {**SAFE_DEFINITION, "url": "https://api.example.com/run"}
        r = await client.post("/api/tools", json={
            "workspace_id": "ws1", "name": "webhook", "kind": "openapi",
            "definition": definition,
        })
        assert r.status_code == 200
        assert r.json()["safety_flag"] == "high_risk_network"


class TestImportTool:
    @pytest.mark.asyncio
    async def test_import_with_valid_checksum(self, client):
        r = await client.post("/api/tools/import", json={
            "workspace_id": "ws1", "name": "shared", "kind": "python",
            "definition": SAFE_DEFINITION, "checksum": _checksum(SAFE_DEFINITION),
        })
        assert r.status_code == 200
        assert r.json()["source"] == "community"

    @pytest.mark.asyncio
    async def test_import_rejects_checksum_mismatch(self, client):
        r = await client.post("/api/tools/import", json={
            "workspace_id": "ws1", "name": "tampered", "kind": "python",
            "definition": SAFE_DEFINITION, "checksum": "0" * 64,
        })
        assert r.status_code == 400


class TestGetDeleteTool:
    @pytest.mark.asyncio
    async def test_get_missing_returns_404(self, client):
        r = await client.get("/api/tools/nope")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_tool(self, client):
        created = (await client.post("/api/tools", json={
            "workspace_id": "ws1", "name": "temp", "kind": "python",
            "definition": SAFE_DEFINITION,
        })).json()
        assert (await client.delete(f"/api/tools/{created['id']}")).status_code == 204
        assert (await client.get(f"/api/tools/{created['id']}")).status_code == 404

    @pytest.mark.asyncio
    async def test_list_filters_by_workspace(self, client):
        for ws in ("ws1", "ws2"):
            await client.post("/api/tools", json={
                "workspace_id": ws, "name": f"tool-{ws}", "kind": "python",
                "definition": SAFE_DEFINITION,
            })
        r = await client.get("/api/tools", params={"workspace_id": "ws1"})
        assert len(r.json()) == 1
