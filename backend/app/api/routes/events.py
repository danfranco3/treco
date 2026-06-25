import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AgentStatus, EventType
from app.core.database import get_db
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.services.auth import resolve_agent
from app.services.deviation_detector import check_post_event

router = APIRouter()


async def _fetch_ticket(ticket_id: str, db: AsyncSession) -> "Ticket | None":
    return await db.get(Ticket, ticket_id)


def _workspace_events_query(workspace_id: str):
    return select(AgentEvent).where(AgentEvent.workspace_id == workspace_id)


class EventRequest(BaseModel):
    ticket_id: str = Field(..., description="ID of the ticket this event is associated with.", examples=["39a47894-f482-4bb2-906c-13227d2e500e"])
    event_type: Literal["ticket_started", "criterion_checked", "criterion_failed", "pr_opened", "done", "error", "log", "heartbeat", "deviation"] = Field(
        ...,
        description=(
            "Type of event. Key types:\n"
            "- `ticket_started` — agent begins work; sets ticket status to `in_progress`\n"
            "- `criterion_checked` — marks an acceptance criterion as done (requires `criterion_id`)\n"
            "- `criterion_failed` — agent could not satisfy a criterion\n"
            "- `pr_opened` — agent opened a pull request\n"
            "- `done` — agent finished; sets ticket status to `done`\n"
            "- `error` — agent hit an unrecoverable error\n"
            "- `log` — free-form agent log message\n"
            "- `heartbeat` — agent keepalive (updates `last_seen_at`)\n"
            "- `deviation` — agent detected or was detected to be off-track"
        ),
        examples=["criterion_checked"],
    )
    criterion_id: str | None = Field(None, description="Acceptance criterion ID to mark done. Required for `criterion_checked` events.", examples=["crit-001"])
    tokens_in: int = Field(0, description="Input tokens consumed in this LLM call.", examples=[512])
    tokens_out: int = Field(0, description="Output tokens generated in this LLM call.", examples=[128])
    model: str | None = Field(None, description="LLM model used for this call.", examples=["claude-haiku-4-5-20251001"])
    payload: dict = Field(default={}, description="Arbitrary event metadata. Schema is event-type specific.")


class EventResponse(BaseModel):
    id: str
    agent_id: str
    ticket_id: str
    workspace_id: str
    event_type: str
    criterion_id: str | None
    tokens_in: int
    tokens_out: int
    model: str | None
    payload: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CostSummary(BaseModel):
    ticket_id: str
    total_tokens_in: int
    total_tokens_out: int
    event_count: int


@router.post(
    "",
    summary="Post an agent event",
    description=(
        "Append an event to the agent event log. Authenticated by `X-Agent-Key` header. "
        "Side effects depend on `event_type`: `ticket_started` sets ticket to `in_progress`, "
        "`criterion_checked` marks a criterion done, `done`/`error` closes the agent run. "
        "Events are append-only and cannot be modified or deleted."
    ),
)
async def post_event(
    req: EventRequest,
    x_agent_key: str = Header(..., alias="X-Agent-Key", description="Raw agent API key issued at agent creation."),
    db: AsyncSession = Depends(get_db),
):
    agent = await resolve_agent(x_agent_key, db)
    agent.last_seen_at = datetime.utcnow()

    event = AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=req.ticket_id,
        workspace_id=agent.workspace_id,
        event_type=req.event_type,
        criterion_id=req.criterion_id,
        tokens_in=req.tokens_in,
        tokens_out=req.tokens_out,
        model=req.model,
        payload=req.payload,
    )
    db.add(event)

    if req.event_type == EventType.TICKET_STARTED:
        agent.status = AgentStatus.WORKING
        agent.current_ticket_id = req.ticket_id
        ticket = await _fetch_ticket(req.ticket_id, db)
        if ticket:
            ticket.status = "in_progress"
            db.add(ticket)
    elif req.event_type in (EventType.DONE, EventType.ERROR):
        agent.status = AgentStatus.IDLE if req.event_type == EventType.DONE else AgentStatus.ERROR
        agent.current_ticket_id = None
        if req.event_type == EventType.DONE:
            ticket = await _fetch_ticket(req.ticket_id, db)
            if ticket:
                ticket.status = "done"
                db.add(ticket)
    elif req.event_type == EventType.CRITERION_CHECKED and req.criterion_id:
        ticket = await _fetch_ticket(req.ticket_id, db)
        if ticket and ticket.acceptance_criteria:
            # Deep copy required: shallow list() shares dict refs, so in-place
            # mutation of c["done"] would also mutate the "committed" state
            # SQLAlchemy cached, making the column appear unmodified.
            criteria = [dict(c) for c in ticket.acceptance_criteria]
            for c in criteria:
                if c.get("id") == req.criterion_id:
                    c["done"] = True
                    break
            ticket.acceptance_criteria = criteria
            db.add(ticket)

    await db.commit()

    if req.event_type in (EventType.DONE, EventType.LOG, EventType.ERROR):
        deviations = await check_post_event(event, agent, db)
        if deviations:
            for dev in deviations:
                db.add(dev)
            await db.commit()

    return {"id": event.id}


@router.get(
    "/ticket/{ticket_id}",
    response_model=list[EventResponse],
    summary="List events for a ticket",
    description="Return all events for a ticket, ordered by creation time (oldest first).",
)
async def get_ticket_events(ticket_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.ticket_id == ticket_id)
        .order_by(AgentEvent.created_at)
    )
    return result.scalars().all()


@router.get(
    "/ticket/{ticket_id}/cost",
    response_model=CostSummary,
    summary="Get token cost summary for a ticket",
    description="Aggregate `tokens_in` and `tokens_out` across all events for this ticket. Cost is computed at read time — never persisted.",
)
async def get_ticket_cost(ticket_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.sum(AgentEvent.tokens_in),
            func.sum(AgentEvent.tokens_out),
            func.count(AgentEvent.id),
        ).where(AgentEvent.ticket_id == ticket_id)
    )
    tokens_in, tokens_out, count = result.one()
    return CostSummary(
        ticket_id=ticket_id,
        total_tokens_in=tokens_in or 0,
        total_tokens_out=tokens_out or 0,
        event_count=count or 0,
    )


@router.get(
    "/agent/{agent_id}",
    response_model=list[EventResponse],
    summary="List events for an agent",
    description="Return events emitted by a specific agent, ordered by creation time (newest first). `limit` is capped at 500.",
)
async def get_agent_events(
    agent_id: str,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.agent_id == agent_id)
        .order_by(AgentEvent.created_at.desc())
        .limit(min(limit, 500))
    )
    return result.scalars().all()


@router.get(
    "",
    response_model=list[EventResponse],
    summary="List events for a workspace",
    description="Return events for all agents in a workspace, ordered by creation time (newest first). `limit` is capped at 500.",
)
async def list_workspace_events(
    workspace_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        _workspace_events_query(workspace_id)
        .order_by(AgentEvent.created_at.desc())
        .limit(min(limit, 500))
    )
    return result.scalars().all()


def _event_to_dict(event: AgentEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "agent_id": event.agent_id,
        "ticket_id": event.ticket_id,
        "workspace_id": event.workspace_id,
        "event_type": event.event_type,
        "criterion_id": event.criterion_id,
        "tokens_in": event.tokens_in,
        "tokens_out": event.tokens_out,
        "model": event.model,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }


@router.get(
    "/stream",
    summary="SSE stream of workspace events",
    description=(
        "Server-Sent Events stream for real-time event delivery. "
        "Bootstraps with the last 50 events on connect, then delivers new events as they arrive. "
        "Sends a keepalive comment every 15 seconds. "
        "Connect with `EventSource` in the browser or `httpx` with streaming enabled."
    ),
)
async def event_stream(workspace_id: str, db: AsyncSession = Depends(get_db)):
    async def generator():
        result = await db.execute(
            _workspace_events_query(workspace_id)
            .order_by(AgentEvent.created_at.desc())
            .limit(50)
        )
        bootstrap = list(reversed(result.scalars().all()))
        for event in bootstrap:
            yield {"data": json.dumps(_event_to_dict(event))}

        last_created = bootstrap[-1].created_at if bootstrap else None
        tick = 0

        while True:
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                return

            tick += 1
            if tick % 30 == 0:
                yield {"comment": "keepalive"}

            q = _workspace_events_query(workspace_id).order_by(AgentEvent.created_at)
            if last_created is not None:
                q = q.where(AgentEvent.created_at > last_created)
            result = await db.execute(q)
            for event in result.scalars().all():
                yield {"data": json.dumps(_event_to_dict(event))}
                last_created = event.created_at

    return EventSourceResponse(generator())
