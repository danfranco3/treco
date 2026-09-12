"""Metric recording — pre-aggregated telemetry_events rows.

record_metric() rides along wherever events are already written; final
per-ticket economics are rolled up once, on done/error, so dashboards never
re-scan agent_events.
"""
import logging
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.pubsub import bus, telemetry_channel, telemetry_to_dict
from app.models.event import AgentEvent
from app.models.telemetry_event import TelemetryEvent

logger = logging.getLogger(__name__)


def cost_usd(model: str | None, tokens_in: int, tokens_out: int) -> float | None:
    """USD cost from the configured $/1M-token price table, matched by model prefix."""
    if not model:
        return None
    for prefix, price in settings.model_prices.items():
        if model.startswith(prefix):
            return (tokens_in * price["in"] + tokens_out * price["out"]) / 1_000_000
    return None


async def record_metric(
    workspace_id: str,
    metric: str,
    value: float,
    unit: str,
    *,
    ticket_id: str | None = None,
    agent_id: str | None = None,
    dims: dict[str, Any] | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        row = TelemetryEvent(
            workspace_id=workspace_id,
            ticket_id=ticket_id,
            agent_id=agent_id,
            metric=metric,
            value=value,
            unit=unit,
            dims=dims or {},
        )
        db.add(row)
        await db.commit()
        bus.publish(telemetry_channel(workspace_id), telemetry_to_dict(row))


async def record_ticket_final_metrics(ticket_id: str, workspace_id: str, agent_id: str) -> None:
    """Roll up per-ticket economics once, when the run ends."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    func.sum(AgentEvent.tokens_in),
                    func.sum(AgentEvent.tokens_out),
                    func.min(AgentEvent.created_at),
                    func.max(AgentEvent.created_at),
                ).where(AgentEvent.ticket_id == ticket_id)
            )
            tokens_in, tokens_out, first_at, last_at = result.one()

            model_result = await db.execute(
                select(AgentEvent.model).where(
                    AgentEvent.ticket_id == ticket_id, AgentEvent.model.is_not(None)
                ).limit(1)
            )
            model = model_result.scalar()

            interventions = await db.execute(
                select(func.count(AgentEvent.id)).where(
                    AgentEvent.ticket_id == ticket_id,
                    AgentEvent.event_type == "permission_requested",
                )
            )
            intervention_count = interventions.scalar() or 0

        tokens_in = tokens_in or 0
        tokens_out = tokens_out or 0
        common: dict[str, Any] = {"ticket_id": ticket_id, "agent_id": agent_id}

        await record_metric(workspace_id, "tokens_in_per_ticket", tokens_in, "tokens", **common)
        await record_metric(workspace_id, "tokens_out_per_ticket", tokens_out, "tokens", **common)
        usd = cost_usd(model, tokens_in, tokens_out)
        if usd is not None:
            await record_metric(
                workspace_id, "cost_usd_per_ticket", usd, "usd",
                dims={"model": model}, **common,
            )
        if first_at and last_at:
            await record_metric(
                workspace_id, "time_to_completion",
                (last_at - first_at).total_seconds() * 1000, "ms", **common,
            )
        await record_metric(
            workspace_id, "interventions_per_ticket", intervention_count, "count", **common,
        )
        if tokens_in > 0:
            await record_metric(
                workspace_id, "token_efficiency_ratio", tokens_out / tokens_in, "ratio", **common,
            )
    except Exception:
        logger.exception("Final metric rollup failed for ticket %s", ticket_id)
