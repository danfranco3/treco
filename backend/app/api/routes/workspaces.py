from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.models.workspace import Workspace

router = APIRouter()


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    repo_path: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = Field(None)
    repo_path: str | None = Field(None)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workspace).order_by(Workspace.created_at))
    return result.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Workspace, workspace_id)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    req: UpdateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    workspace = await get_or_404(db, Workspace, workspace_id)
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=422, detail="name must not be blank")
        workspace.name = req.name.strip()
    if req.repo_path is not None:
        workspace.repo_path = req.repo_path.strip() or None
    await db.commit()
    await db.refresh(workspace)
    return workspace
