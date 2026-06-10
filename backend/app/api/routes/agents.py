import asyncio
import hashlib
import json
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.agent import Agent
from app.models.event import AgentEvent

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


@router.post("/", response_model=CreateAgentResponse)
async def create_agent(req: CreateAgentRequest, db: AsyncSession = Depends(get_db)):
    raw_key = settings.sdk_key_prefix + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    agent = Agent(
        id=str(uuid.uuid4()),
        workspace_id=req.workspace_id,
        name=req.name,
        api_key_hash=key_hash,
        status="idle",
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


@router.get("/")
async def list_agents(workspace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Agent).where(Agent.workspace_id == workspace_id)
    )
    return result.scalars().all()


@router.get("/me", response_model=AgentResponse)
async def get_me(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
    db: AsyncSession = Depends(get_db),
):
    key_hash = hashlib.sha256(x_agent_key.encode()).hexdigest()
    result = await db.execute(select(Agent).where(Agent.api_key_hash == key_hash))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent API key")
    return agent


@router.get("/stream")
async def agent_stream(workspace_id: str, db: AsyncSession = Depends(get_db)):
    async def generator():
        last_snapshot: dict[str, str] = {}
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
            await asyncio.sleep(0.5)

    return EventSourceResponse(generator())


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


class AssignRequest(BaseModel):
    ticket_id: str


@router.post("/{agent_id}/assign")
async def assign_ticket(
    agent_id: str,
    req: AssignRequest,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status == "working":
        raise HTTPException(status_code=409, detail="Agent already working on a ticket")

    agent.status = "working"
    agent.current_ticket_id = req.ticket_id
    agent.last_seen_at = datetime.utcnow()
    db.add(agent)

    event = AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=req.ticket_id,
        workspace_id=agent.workspace_id,
        event_type="ticket_started",
        payload={"source": "ui_assign"},
    )
    db.add(event)
    await db.commit()
    return {"ok": True}
