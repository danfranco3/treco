import asyncio
import json
import os
import signal
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AgentStatus, EventType
from app.core.database import get_db, get_or_404
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.services.auth import generate_api_key, resolve_agent

router = APIRouter()


def _agents_in_workspace(workspace_id: str):
    return select(Agent).where(Agent.workspace_id == workspace_id)


class CreateAgentRequest(BaseModel):
    workspace_id: str = Field(..., description="Workspace this agent belongs to.", examples=["ws-abc123"])
    name: str = Field(..., description="Human-readable agent name. Must be unique within the workspace.", examples=["agent-fix-login"])


class AgentResponse(BaseModel):
    id: str
    name: str
    status: str
    current_ticket_id: str | None
    workspace_id: str
    last_seen_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateAgentResponse(AgentResponse):
    api_key: str  # returned only on creation, never again


@router.post(
    "",
    response_model=CreateAgentResponse,
    summary="Create an agent",
    description=(
        "Create a new agent in a workspace. Returns the agent record including its raw `api_key`. "
        "**The raw key is returned exactly once and never stored.** The agent uses it to authenticate "
        "SDK calls via the `X-Agent-Key` header."
    ),
)
async def create_agent(req: CreateAgentRequest, db: AsyncSession = Depends(get_db)):
    raw_key, key_hash = generate_api_key()
    agent = Agent(
        id=str(uuid.uuid4()),
        workspace_id=req.workspace_id,
        name=req.name,
        api_key_hash=key_hash,
        status=AgentStatus.IDLE,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return CreateAgentResponse(
        id=agent.id,
        name=agent.name,
        status=agent.status,
        current_ticket_id=agent.current_ticket_id,
        workspace_id=agent.workspace_id,
        api_key=raw_key,
    )


@router.get(
    "",
    response_model=list[AgentResponse],
    summary="List agents in a workspace",
    description="Return all agents belonging to a workspace. `status` is one of `idle`, `working`, `offline`, `error`.",
)
async def list_agents(workspace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_agents_in_workspace(workspace_id))
    return result.scalars().all()


@router.get(
    "/me",
    response_model=AgentResponse,
    summary="Identify the calling agent",
    description="Return the agent record associated with the `X-Agent-Key` header. Used by the SDK to self-identify on startup.",
)
async def get_me(
    x_agent_key: str = Header(..., alias="X-Agent-Key", description="Raw agent API key issued at agent creation."),
    db: AsyncSession = Depends(get_db),
):
    return await resolve_agent(x_agent_key, db)


@router.get(
    "/stream",
    summary="SSE stream of agent status changes",
    description=(
        "Server-Sent Events stream that delivers agent status updates in real time. "
        "Only sends an event when an agent's `status` or `current_ticket_id` changes. "
        "Sends a keepalive comment every 15 seconds."
    ),
)
async def agent_stream(workspace_id: str, db: AsyncSession = Depends(get_db)):
    async def generator():
        last_snapshot: dict[str, str] = {}
        tick = 0
        while True:
            result = await db.execute(
                _agents_in_workspace(workspace_id)
            )
            for agent in result.scalars().all():
                key = f"{agent.status}:{agent.current_ticket_id}"
                if last_snapshot.get(agent.id) != key:
                    last_snapshot[agent.id] = key
                    yield {
                        "data": json.dumps({
                            "id": agent.id,
                            "name": agent.name,
                            "status": agent.status,
                            "current_ticket_id": agent.current_ticket_id,
                            "workspace_id": agent.workspace_id,
                        })
                    }
            tick += 1
            if tick % 30 == 0:
                yield {"comment": "keepalive"}
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                return

    return EventSourceResponse(generator())


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get an agent",
    description="Retrieve a single agent by ID. Returns 404 if not found.",
)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Agent, agent_id)


@router.post(
    "/{agent_id}/cancel",
    response_model=AgentResponse,
    summary="Cancel a running agent",
    description=(
        "Send SIGTERM to the agent's process (if `pid` is set), reset status to `idle`, "
        "and emit an `error` event with `reason: cancelled`. Safe to call on an already-idle agent."
    ),
)
async def cancel_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await get_or_404(db, Agent, agent_id)
    ticket_id = agent.current_ticket_id

    if agent.pid is not None:
        try:
            os.kill(agent.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    agent.status = AgentStatus.IDLE
    agent.pid = None
    agent.current_ticket_id = None
    db.add(agent)

    if ticket_id:
        db.add(AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            ticket_id=ticket_id,
            workspace_id=agent.workspace_id,
            event_type=EventType.ERROR,
            payload={"reason": "cancelled"},
        ))

    await db.commit()
    await db.refresh(agent)
    return agent


class AssignRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID to assign to this agent.", examples=["39a47894-f482-4bb2-906c-13227d2e500e"])


@router.post(
    "/{agent_id}/assign",
    summary="Assign a ticket to an agent",
    description="Assign a ticket to an agent from the dashboard UI. Emits a `ticket_started` event and sets agent status to `working`. Returns 409 if the agent is already working.",
)
async def assign_ticket(
    agent_id: str,
    req: AssignRequest,
    db: AsyncSession = Depends(get_db),
):
    agent = await get_or_404(db, Agent, agent_id)
    if agent.status == AgentStatus.WORKING:
        raise HTTPException(status_code=409, detail="Agent already working on a ticket")

    agent.status = AgentStatus.WORKING
    agent.current_ticket_id = req.ticket_id
    agent.last_seen_at = datetime.utcnow()
    db.add(agent)

    event = AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=req.ticket_id,
        workspace_id=agent.workspace_id,
        event_type=EventType.TICKET_STARTED,
        payload={"source": "ui_assign"},
    )
    db.add(event)
    await db.commit()
    return {"ok": True}
