import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AgentStatus
from app.core.database import get_db
from app.models.agent import Agent
from app.models.workspace import Workspace
from app.services.auth import generate_api_key

router = APIRouter()


class InitRequest(BaseModel):
    workspace_id: str
    agent_name: str


class InitResponse(BaseModel):
    agent_id: str
    api_key: str
    workspace_id: str


@router.post("/", response_model=InitResponse)
async def init_workspace(req: InitRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Agent).where(
            Agent.name == req.agent_name,
            Agent.workspace_id == req.workspace_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Agent with this name already exists in workspace. Use a different name or delete the existing agent.",
        )

    workspace = await db.get(Workspace, req.workspace_id)
    if not workspace:
        workspace = Workspace(id=req.workspace_id, name=req.workspace_id, repo_path=None)
        db.add(workspace)
        await db.commit()

    raw_key, key_hash = generate_api_key()

    agent = Agent(
        id=str(uuid.uuid4()),
        workspace_id=req.workspace_id,
        name=req.agent_name,
        api_key_hash=key_hash,
        status=AgentStatus.IDLE,
    )
    db.add(agent)
    await db.commit()

    return InitResponse(agent_id=agent.id, api_key=raw_key, workspace_id=req.workspace_id)
