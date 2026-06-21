import asyncio
import json
import os
import signal
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AgentStatus, EventType
from app.core.database import get_db, get_or_404
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.user import User
from app.models.user_workspace import UserWorkspace
from app.services.auth import check_workspace_member, generate_api_key, require_user, resolve_agent

router = APIRouter()


class CreateAgentRequest(BaseModel):
    workspace_id: str
    name: str


class AgentResponse(BaseModel):
    id: str
    name: str
    status: str
    current_ticket_id: str | None
    workspace_id: str

    model_config = ConfigDict(from_attributes=True)


class CreateAgentResponse(AgentResponse):
    api_key: str  # returned only on creation, never again


@router.post("", response_model=CreateAgentResponse)
async def create_agent(
    req: CreateAgentRequest,
    current_user: Annotated[User, Depends(require_user)],
    db: AsyncSession = Depends(get_db),
):
    await check_workspace_member(current_user.id, req.workspace_id, db)

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


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    workspace_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: AsyncSession = Depends(get_db),
):
    await check_workspace_member(current_user.id, workspace_id, db)
    result = await db.execute(
        select(Agent).where(Agent.workspace_id == workspace_id)
    )
    return result.scalars().all()


@router.get("/me", response_model=AgentResponse)
async def get_me(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
    db: AsyncSession = Depends(get_db),
):
    return await resolve_agent(x_agent_key, db)


@router.get("/stream")
async def agent_stream(
    workspace_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: AsyncSession = Depends(get_db),
):
    await check_workspace_member(current_user.id, workspace_id, db)

    async def generator():
        last_snapshot: dict[str, str] = {}
        tick = 0
        while True:
            result = await db.execute(
                select(Agent).where(Agent.workspace_id == workspace_id)
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


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Agent, agent_id)


@router.post("/{agent_id}/cancel", response_model=AgentResponse)
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
    ticket_id: str


@router.post("/{agent_id}/assign")
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
