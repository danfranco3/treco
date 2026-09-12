"""DEMO_MODE must block every mutating verb — routes enumerated from the app,
never hand-listed, so newly added routes are covered automatically."""
import re

import pytest

from app.core.config import settings
from app.main import app

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _mutating_routes() -> list[tuple[str, str]]:
    # Enumerated via the OpenAPI schema, not router internals — route class
    # layout changes across FastAPI/Starlette versions, the schema does not.
    routes: set[tuple[str, str]] = set()
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            if method.upper() in MUTATING:
                routes.add((method.upper(), re.sub(r"\{[^}]+\}", "test-id", path)))
    return sorted(routes)


class TestRouteEnumeration:
    def test_enumeration_sees_old_and_new_modules(self):
        paths = {p for _, p in _mutating_routes()}
        assert any(p.startswith("/api/tickets") for p in paths)
        assert any(p.startswith("/api/agents") for p in paths)
        assert any(p.startswith("/api/events") for p in paths)
        assert any(p.startswith("/api/integrations") for p in paths)
        assert any(p.startswith("/api/tools") for p in paths)

    def test_enumeration_is_not_empty(self):
        assert len(_mutating_routes()) >= 10


class TestDemoModeBlocksMutations:
    @pytest.mark.asyncio
    async def test_every_mutating_route_returns_403_when_demo_mode_on(
        self, client, service_sessions, monkeypatch
    ):
        monkeypatch.setattr(settings, "demo_mode", True)
        for method, path in _mutating_routes():
            r = await client.request(method, path, json={})
            assert r.status_code == 403, (
                f"{method} {path} not blocked in demo mode (got {r.status_code})"
            )
            assert r.json()["detail"] == "This is a read-only demo instance."

    @pytest.mark.asyncio
    async def test_reads_still_allowed_when_demo_mode_on(
        self, client, service_sessions, monkeypatch
    ):
        monkeypatch.setattr(settings, "demo_mode", True)
        assert (await client.get("/api/tickets")).status_code == 200
        assert (await client.get("/api/meta/tier")).status_code == 200
        assert (await client.get("/api/workspaces")).status_code == 200

    @pytest.mark.asyncio
    async def test_mutations_allowed_when_demo_mode_off(self, client):
        assert settings.demo_mode is False
        r = await client.post("/api/tickets", json={"title": "not blocked"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_block_recorded_as_telemetry_metric(
        self, client, service_sessions, monkeypatch
    ):
        monkeypatch.setattr(settings, "demo_mode", True)
        await client.post("/api/tickets", json={})
        r = await client.get("/api/telemetry/workspace/global/summary")
        metrics = {row["metric"] for row in r.json()}
        assert "demo_mode_block" in metrics
