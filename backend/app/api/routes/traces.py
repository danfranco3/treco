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
from app.core.pubsub import bus, trace_channel
from app.models.trace import Trace

router = APIRouter()


class TraceNode(BaseModel):
    id: str
    agent_id: str
    ticket_id: str
    parent_trace_id: str | None
    event_id: str | None
    step_type: str
    tool_name: str | None
    status: str
    tokens_in: int
    tokens_out: int
    duration_ms: int | None
    payload: dict[str, Any]
    created_at: datetime
    children: list["TraceNode"] = []

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/ticket/{ticket_id}",
    response_model=list[TraceNode],
    summary="Get the trace tree for a ticket",
    description="All trace steps for a ticket, nested by parent_trace_id, ordered by creation time.",
)
async def get_ticket_traces(ticket_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Trace).where(Trace.ticket_id == ticket_id).order_by(Trace.created_at)
    )
    nodes = {t.id: TraceNode.model_validate(t) for t in result.scalars().all()}
    roots: list[TraceNode] = []
    for node in nodes.values():
        parent = nodes.get(node.parent_trace_id) if node.parent_trace_id else None
        if parent:
            parent.children.append(node)
        else:
            roots.append(node)
    return roots


@router.get(
    "/stream",
    summary="SSE stream of trace steps",
    description=(
        "Live Server-Sent Events stream of trace steps for a workspace. "
        "No bootstrap — connect before starting a run, or fetch history via "
        "`GET /traces/ticket/{id}`. Keepalive comment every 15 seconds."
    ),
)
async def trace_stream(workspace_id: str):
    async def generator():
        with bus.subscribe(trace_channel(workspace_id)) as sub:
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
