import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.models.user import User
from app.models.user_workspace import UserWorkspace
from app.models.workspace import Workspace
from app.services.auth import check_workspace_member, require_user

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str
    repo_path: str

    @field_validator("name", "repo_path")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    repo_path: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberResponse(BaseModel):
    user_id: str
    workspace_id: str
    role: str
    login: str
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "member"

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("owner", "member"):
            raise ValueError("role must be 'owner' or 'member'")
        return v


def _validate_git_repo(repo_path: str) -> Path:
    path = Path(repo_path).resolve()
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path does not exist or is not a directory: {repo_path}")

    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Not a git repository: {repo_path}")
    return path


async def _require_member(
    workspace_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserWorkspace:
    await get_or_404(db, Workspace, workspace_id)
    return await check_workspace_member(current_user.id, workspace_id, db)


async def _require_owner(
    membership: Annotated[UserWorkspace, Depends(_require_member)],
) -> UserWorkspace:
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Workspace owner required")
    return membership


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    req: CreateWorkspaceRequest,
    current_user: Annotated[User, Depends(require_user)],
    db: AsyncSession = Depends(get_db),
):
    resolved = _validate_git_repo(req.repo_path)

    workspace = Workspace(
        id=str(uuid.uuid4()),
        name=req.name,
        repo_path=str(resolved),
    )
    db.add(workspace)
    await db.flush()

    membership = UserWorkspace(
        user_id=current_user.id,
        workspace_id=workspace.id,
        role="owner",
    )
    db.add(membership)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: Annotated[User, Depends(require_user)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace)
        .join(UserWorkspace, UserWorkspace.workspace_id == Workspace.id)
        .where(UserWorkspace.user_id == current_user.id)
        .order_by(Workspace.created_at)
    )
    return result.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    _: Annotated[UserWorkspace, Depends(_require_member)],
    db: AsyncSession = Depends(get_db),
):
    return await get_or_404(db, Workspace, workspace_id)


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    repo_path: str | None = None


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    req: UpdateWorkspaceRequest,
    _: Annotated[UserWorkspace, Depends(_require_member)],
    db: AsyncSession = Depends(get_db),
):
    workspace = await get_or_404(db, Workspace, workspace_id)

    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=422, detail="name must not be blank")
        workspace.name = req.name
    if req.repo_path is not None:
        resolved = _validate_git_repo(req.repo_path)
        workspace.repo_path = str(resolved)

    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    _: Annotated[UserWorkspace, Depends(_require_owner)],
    db: AsyncSession = Depends(get_db),
):
    workspace = await get_or_404(db, Workspace, workspace_id)
    await db.delete(workspace)
    await db.commit()


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(
    workspace_id: str,
    _: Annotated[UserWorkspace, Depends(_require_member)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserWorkspace, User)
        .join(User, User.id == UserWorkspace.user_id)
        .where(UserWorkspace.workspace_id == workspace_id)
        .order_by(UserWorkspace.created_at)
    )
    rows = result.all()
    return [
        MemberResponse(
            user_id=m.user_id,
            workspace_id=m.workspace_id,
            role=m.role,
            login=u.login,
            avatar_url=u.avatar_url,
        )
        for m, u in rows
    ]


@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    workspace_id: str,
    req: AddMemberRequest,
    _: Annotated[UserWorkspace, Depends(_require_owner)],
    db: AsyncSession = Depends(get_db),
):
    await get_or_404(db, Workspace, workspace_id)

    target_user = await db.get(User, req.user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await db.execute(
        select(UserWorkspace).where(
            UserWorkspace.user_id == req.user_id,
            UserWorkspace.workspace_id == workspace_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User is already a member")

    membership = UserWorkspace(
        user_id=req.user_id,
        workspace_id=workspace_id,
        role=req.role,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return MemberResponse(
        user_id=membership.user_id,
        workspace_id=membership.workspace_id,
        role=membership.role,
        login=target_user.login,
        avatar_url=target_user.avatar_url,
    )


@router.delete("/{workspace_id}/members/{target_user_id}", status_code=204)
async def remove_member(
    workspace_id: str,
    target_user_id: str,
    current_membership: Annotated[UserWorkspace, Depends(_require_owner)],
    db: AsyncSession = Depends(get_db),
):
    # Owner cannot remove themselves — workspace must always have at least one owner
    if target_user_id == current_membership.user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the workspace")

    result = await db.execute(
        select(UserWorkspace).where(
            UserWorkspace.user_id == target_user_id,
            UserWorkspace.workspace_id == workspace_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(membership)
    await db.commit()
