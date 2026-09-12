"""Tests for telemetry read endpoints and the metric-recording service."""
import uuid

import pytest
from sqlalchemy import select

from app.models.event import AgentEvent
from app.models.telemetry_event import TelemetryEvent
from app.services.telemetry import cost_usd, record_metric, record_ticket_final_metrics
from tests.shared import TestSessionLocal


async def _seed_metric(workspace_id: str, metric: str, value: float, ticket_id: str | None = None):
    async with TestSessionLocal() as db:
        db.add(TelemetryEvent(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            ticket_id=ticket_id,
            metric=metric,
            value=value,
            unit="count",
            dims={},
        ))
        await db.commit()


class TestWorkspaceSummary:
    @pytest.mark.asyncio
    async def test_summary_returns_latest_value_per_metric(self, client):
        await _seed_metric("ws1", "loop_count_per_ticket", 5)
        await _seed_metric("ws1", "loop_count_per_ticket", 12)
        await _seed_metric("ws1", "interventions_per_ticket", 2)
        await _seed_metric("ws2", "loop_count_per_ticket", 99)

        r = await client.get("/api/telemetry/workspace/ws1/summary")
        assert r.status_code == 200
        by_metric = {row["metric"]: row["value"] for row in r.json()}
        assert by_metric["loop_count_per_ticket"] == 12
        assert by_metric["interventions_per_ticket"] == 2

    @pytest.mark.asyncio
    async def test_empty_workspace_returns_empty_list(self, client):
        r = await client.get("/api/telemetry/workspace/empty/summary")
        assert r.status_code == 200
        assert r.json() == []


class TestTicketMetrics:
    @pytest.mark.asyncio
    async def test_ticket_series_is_time_ordered(self, client):
        await _seed_metric("ws1", "diff_churn_lines", 10, ticket_id="t1")
        await _seed_metric("ws1", "diff_churn_lines", 30, ticket_id="t1")
        await _seed_metric("ws1", "diff_churn_lines", 7, ticket_id="t2")

        r = await client.get("/api/telemetry/ticket/t1")
        assert r.status_code == 200
        values = [row["value"] for row in r.json()]
        assert values == [10, 30]


class TestCostUsd:
    def test_matches_model_by_prefix(self):
        # claude-sonnet: $3/M in, $15/M out
        assert cost_usd("claude-sonnet-5", 1_000_000, 1_000_000) == 18.0

    def test_unknown_model_returns_none(self):
        assert cost_usd("mystery-model-9", 1000, 1000) is None

    def test_none_model_returns_none(self):
        assert cost_usd(None, 1000, 1000) is None

    def test_zero_tokens_costs_zero(self):
        assert cost_usd("claude-haiku-4-5-20251001", 0, 0) == 0.0


class TestRecordMetric:
    @pytest.mark.asyncio
    async def test_writes_row_with_dims(self, service_sessions):
        await record_metric("ws1", "diff_churn_lines", 42, "count",
                            ticket_id="t1", agent_id="a1", dims={"path": "x.py"})
        async with TestSessionLocal() as db:
            row = (await db.execute(
                select(TelemetryEvent).where(TelemetryEvent.metric == "diff_churn_lines")
            )).scalars().one()
        assert row.value == 42
        assert row.dims == {"path": "x.py"}
        assert row.ticket_id == "t1"


class TestFinalMetricsRollup:
    async def _seed_event(self, ticket_id, event_type="log", tokens_in=0,
                          tokens_out=0, model=None):
        async with TestSessionLocal() as db:
            db.add(AgentEvent(
                id=str(uuid.uuid4()), agent_id="a1", ticket_id=ticket_id,
                workspace_id="ws1", event_type=event_type,
                tokens_in=tokens_in, tokens_out=tokens_out, model=model,
                payload={},
            ))
            await db.commit()

    @pytest.mark.asyncio
    async def test_rolls_up_tokens_cost_and_interventions(self, service_sessions):
        ticket_id = str(uuid.uuid4())
        await self._seed_event(ticket_id, tokens_in=1_000_000, tokens_out=500_000,
                               model="claude-haiku-4-5-20251001")
        await self._seed_event(ticket_id, event_type="permission_requested")
        await self._seed_event(ticket_id, event_type="done")

        await record_ticket_final_metrics(ticket_id, "ws1", "a1")

        async with TestSessionLocal() as db:
            rows = (await db.execute(
                select(TelemetryEvent).where(TelemetryEvent.ticket_id == ticket_id)
            )).scalars().all()
        by_metric = {r.metric: r for r in rows}
        assert by_metric["tokens_in_per_ticket"].value == 1_000_000
        assert by_metric["tokens_out_per_ticket"].value == 500_000
        # haiku: $1/M in + $5/M out → 1.0 + 2.5
        assert by_metric["cost_usd_per_ticket"].value == pytest.approx(3.5)
        assert by_metric["interventions_per_ticket"].value == 1
        assert by_metric["token_efficiency_ratio"].value == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_cost_metric_skipped_without_model(self, service_sessions):
        ticket_id = str(uuid.uuid4())
        await self._seed_event(ticket_id, tokens_in=100, tokens_out=10)
        await record_ticket_final_metrics(ticket_id, "ws1", "a1")
        async with TestSessionLocal() as db:
            metrics = {r.metric for r in (await db.execute(
                select(TelemetryEvent).where(TelemetryEvent.ticket_id == ticket_id)
            )).scalars().all()}
        assert "cost_usd_per_ticket" not in metrics
        assert "tokens_in_per_ticket" in metrics

    @pytest.mark.asyncio
    async def test_rollup_failure_never_raises(self, service_sessions, monkeypatch):
        import app.services.telemetry as telemetry_mod

        class Exploding:
            def __call__(self):
                raise RuntimeError("db down")

        monkeypatch.setattr(telemetry_mod, "AsyncSessionLocal", Exploding())
        await record_ticket_final_metrics("t-x", "ws1", "a1")
