import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pubsub import bus, telemetry_channel
from app.models.telemetry_event import TelemetryEvent

router = APIRouter()


class TelemetryEventResponse(BaseModel):
    id: str
    workspace_id: str
    ticket_id: str | None
    agent_id: str | None
    metric: str
    value: float
    unit: str
    dims: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/workspace/{workspace_id}/summary",
    response_model=list[TelemetryEventResponse],
    summary="Latest value per metric for a workspace",
)
async def workspace_summary(workspace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TelemetryEvent)
        .where(TelemetryEvent.workspace_id == workspace_id)
        .order_by(TelemetryEvent.created_at.desc())
        .limit(500)
    )
    latest: dict[str, TelemetryEvent] = {}
    for row in result.scalars().all():
        if row.metric not in latest:
            latest[row.metric] = row
    return sorted(latest.values(), key=lambda r: r.metric)


@router.get(
    "/ticket/{ticket_id}",
    response_model=list[TelemetryEventResponse],
    summary="Metric time series for a ticket",
)
async def ticket_metrics(ticket_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TelemetryEvent)
        .where(TelemetryEvent.ticket_id == ticket_id)
        .order_by(TelemetryEvent.created_at)
    )
    return result.scalars().all()


@router.get(
    "/stream",
    summary="SSE stream of metric rows",
    description="Live stream of telemetry rows for a workspace. Keepalive comment every 15 seconds.",
)
async def telemetry_stream(workspace_id: str):
    async def generator():
        with bus.subscribe(telemetry_channel(workspace_id)) as sub:
            while True:
                try:
                    msg = await sub.get(timeout=15.0)
                except asyncio.CancelledError:
                    return
                if msg is None:
                    yield {"comment": "keepalive"}
                    continue
                yield {"data": json.dumps(msg)}

    return EventSourceResponse(generator())
