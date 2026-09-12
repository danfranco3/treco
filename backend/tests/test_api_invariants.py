"""Structural + behavioral enforcement of the CLAUDE.md invariants:
append-only agent_events, read-time cost, immutable Ticket.body, hashed API
keys, and the (currently open) dashboard auth boundary."""
import hashlib

import pytest

from app.main import app
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from tests.shared import TestSessionLocal


def _openapi_ops(prefix: str) -> list[tuple[str, str, dict]]:
    """(path, METHOD, operation) triples from the OpenAPI schema — stable
    across FastAPI/Starlette versions, unlike router internals."""
    return [
        (path, method.upper(), op)
        for path, ops in app.openapi()["paths"].items()
        if path.startswith(prefix)
        for method, op in ops.items()
    ]


class TestEventStreamAppendOnly:
    def test_no_update_or_delete_route_exists_for_events(self):
        ops = _openapi_ops("/api/events")
        assert ops, "event routes missing from the schema — enumeration broke"
        for path, method, _ in ops:
            assert method not in {"PUT", "PATCH", "DELETE"}, (
                f"agent_events must stay append-only; found {method} at {path}"
            )

    def test_event_model_has_no_updated_at_column(self):
        assert "updated_at" not in AgentEvent.__table__.columns

    @pytest.mark.asyncio
    async def test_existing_events_unchanged_after_later_writes(
        self, client, agent_with_key, ticket
    ):
        _, raw_key = agent_with_key
        r1 = await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "log",
                  "payload": {"message": "first"}},
            headers={"X-Agent-Key": raw_key},
        )
        first_id = r1.json()["id"]
        await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "done", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        events = (await client.get(f"/api/events/ticket/{ticket.id}")).json()
        first = next(e for e in events if e["id"] == first_id)
        assert first["event_type"] == "log"
        assert first["payload"] == {"message": "first"}


class TestCostComputedAtReadTime:
    def test_no_persisted_cost_or_token_totals_on_ticket_or_agent(self):
        for model in (Ticket, Agent):
            cols = set(model.__table__.columns.keys())
            leaked = cols & {"cost", "cost_usd", "total_cost",
                             "total_tokens_in", "total_tokens_out", "tokens_in", "tokens_out"}
            assert not leaked, f"{model.__name__} persists derived cost fields: {leaked}"

    @pytest.mark.asyncio
    async def test_cost_reflects_each_new_event_immediately(
        self, client, agent_with_key, ticket
    ):
        _, raw_key = agent_with_key
        await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "log",
                  "tokens_in": 100, "tokens_out": 40, "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        cost1 = (await client.get(f"/api/events/ticket/{ticket.id}/cost")).json()
        assert cost1["total_tokens_in"] == 100
        assert cost1["total_tokens_out"] == 40

        await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "log",
                  "tokens_in": 50, "tokens_out": 10, "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        cost2 = (await client.get(f"/api/events/ticket/{ticket.id}/cost")).json()
        assert cost2["total_tokens_in"] == 150
        assert cost2["total_tokens_out"] == 50
        assert cost2["event_count"] == cost1["event_count"] + 1


class TestTicketBodyImmutable:
    @pytest.mark.asyncio
    async def test_body_unchanged_by_criteria_update_and_events(
        self, client, agent_with_key
    ):
        _, raw_key = agent_with_key
        created = (await client.post("/api/tickets", json={
            "workspace_id": "ws1", "title": "Immutable body",
            "acceptance_criteria": ["c1"],
        })).json()
        ticket_id = created["id"]
        original_body = created["body"]

        crit_id = created["acceptance_criteria"][0]["id"]
        await client.put(f"/api/tickets/{ticket_id}/criteria", json=[
            {"id": crit_id, "text": "c1 edited", "done": True},
        ])
        await client.post(
            "/api/events",
            json={"ticket_id": ticket_id, "event_type": "criterion_checked",
                  "criterion_id": crit_id, "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        await client.post(
            "/api/events",
            json={"ticket_id": ticket_id, "event_type": "done", "payload": {}},
            headers={"X-Agent-Key": raw_key},
        )
        refreshed = (await client.get(f"/api/tickets/{ticket_id}")).json()
        assert refreshed["body"] == original_body

    def test_no_route_accepts_a_body_field_update(self):
        """No ticket route request model exposes `body` as writable input."""
        spec = app.openapi()
        schemas = spec.get("components", {}).get("schemas", {})
        checked = 0
        for path, method, op in _openapi_ops("/api/tickets"):
            if method not in {"POST", "PUT", "PATCH"}:
                continue
            schema = (
                op.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            ref = schema.get("$ref", "")
            if not ref:
                continue
            checked += 1
            props = schemas.get(ref.rsplit("/", 1)[-1], {}).get("properties", {})
            assert "body" not in props, f"{method} {path} accepts raw body input"
        assert checked > 0, "no ticket request models found — enumeration broke"


class TestApiKeyStorage:
    @pytest.mark.asyncio
    async def test_raw_key_never_stored_only_sha256_hash(self, client):
        r = await client.post("/api/agents", json={
            "workspace_id": "ws1", "name": "hash-check",
        })
        raw_key = r.json()["api_key"]
        agent_id = r.json()["id"]
        async with TestSessionLocal() as db:
            agent = await db.get(Agent, agent_id)
            assert agent.api_key_hash == hashlib.sha256(raw_key.encode()).hexdigest()
            assert raw_key not in agent.api_key_hash

    @pytest.mark.asyncio
    async def test_agent_reads_never_return_key_material(self, client, agent_with_key):
        agent, _ = agent_with_key
        single = (await client.get(f"/api/agents/{agent.id}")).json()
        listing = (await client.get("/api/agents", params={"workspace_id": "ws1"})).json()
        for payload in [single, *listing]:
            assert "api_key" not in payload
            assert "api_key_hash" not in payload


class TestDashboardAuthBoundary:
    """The default single-tenant deployment has NO auth on dashboard routes and
    workspace_id is NOT a security boundary. These tests pin that documented
    state; the strict xfail flips red→green the day auth lands."""

    @pytest.mark.asyncio
    async def test_ticket_reads_succeed_without_credentials(self, client, ticket):
        assert (await client.get("/api/tickets")).status_code == 200
        assert (await client.get(f"/api/tickets/{ticket.id}")).status_code == 200

    @pytest.mark.asyncio
    async def test_workspace_reads_succeed_without_credentials(self, client):
        assert (await client.get("/api/workspaces")).status_code == 200

    @pytest.mark.asyncio
    async def test_workspace_id_is_not_a_security_boundary(
        self, client, agent_with_key, ticket
    ):
        _, raw_key = agent_with_key
        await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "log",
                  "payload": {"message": "visible"}},
            headers={"X-Agent-Key": raw_key},
        )
        r = await client.get("/api/events", params={"workspace_id": "ws1"})
        assert r.status_code == 200
        assert len(r.json()) == 1

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="dashboard auth not implemented — remove this marker when it is",
        strict=True,
    )
    async def test_future_dashboard_auth_rejects_anonymous_workspace_read(self, client):
        r = await client.get("/api/workspaces")
        assert r.status_code == 401


class TestAgentAuthBoundary:
    @pytest.mark.asyncio
    async def test_event_post_rejects_missing_key(self, client, ticket):
        r = await client.post("/api/events", json={
            "ticket_id": ticket.id, "event_type": "log", "payload": {},
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_event_post_rejects_hash_used_as_key(self, client, agent_with_key, ticket):
        agent, raw_key = agent_with_key
        stored_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        r = await client.post(
            "/api/events",
            json={"ticket_id": ticket.id, "event_type": "log", "payload": {}},
            headers={"X-Agent-Key": stored_hash},
        )
        assert r.status_code == 401
