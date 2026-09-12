import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.models.tool import Tool

router = APIRouter()

_NETWORK_MARKERS = ("http://", "https://", "socket", "urllib", "requests.", "fetch(", "httpx")
_FS_MARKERS = ("os.remove", "os.unlink", "shutil.", "rmtree", "open(", "writefile", "fs.")


def _checksum(definition: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()


def _classify_safety(definition: dict[str, Any]) -> str:
    """Keyword scan over the declared implementation — deliberately simple;
    anything matching a network or filesystem primitive gets flagged."""
    blob = json.dumps(definition).lower()
    if any(marker in blob for marker in _NETWORK_MARKERS):
        return "high_risk_network"
    if any(marker in blob for marker in _FS_MARKERS):
        return "high_risk_fs"
    return "unverified"


class CreateToolRequest(BaseModel):
    workspace_id: str | None = None
    name: str = Field(..., examples=["lint_check"])
    kind: Literal["openapi", "python", "javascript"]
    definition: dict[str, Any] = Field(
        ...,
        description="Tool schema — same shape as the built-in tools: name/description/input_schema, plus an entrypoint reference.",
    )


class ImportToolRequest(CreateToolRequest):
    checksum: str = Field(..., description="sha256 of the canonical JSON definition — verified on import.")


class ToolResponse(BaseModel):
    id: str
    name: str
    kind: str
    source: str
    definition: dict[str, Any]
    safety_flag: str
    checksum: str
    installed_at: datetime
    workspace_id: str | None

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "",
    response_model=ToolResponse,
    summary="Register a local tool",
)
async def create_tool(req: CreateToolRequest, db: AsyncSession = Depends(get_db)):
    tool = Tool(
        name=req.name,
        kind=req.kind,
        source="local",
        definition=req.definition,
        safety_flag=_classify_safety(req.definition),
        checksum=_checksum(req.definition),
        workspace_id=req.workspace_id,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.post(
    "/import",
    response_model=ToolResponse,
    summary="Import a community tool",
    description="Verifies the declared checksum against the definition and assigns a safety flag by static scan.",
)
async def import_tool(req: ImportToolRequest, db: AsyncSession = Depends(get_db)):
    if _checksum(req.definition) != req.checksum:
        raise HTTPException(status_code=400, detail="Checksum mismatch — definition may have been tampered with")
    tool = Tool(
        name=req.name,
        kind=req.kind,
        source="community",
        definition=req.definition,
        safety_flag=_classify_safety(req.definition),
        checksum=req.checksum,
        workspace_id=req.workspace_id,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get(
    "",
    response_model=list[ToolResponse],
    summary="List tools in a workspace",
)
async def list_tools(workspace_id: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Tool)
    if workspace_id is not None:
        query = query.where(Tool.workspace_id == workspace_id)
    result = await db.execute(query.order_by(Tool.installed_at.desc()))
    return result.scalars().all()


@router.get(
    "/{tool_id}",
    response_model=ToolResponse,
    summary="Get a tool",
)
async def get_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Tool, tool_id)


@router.delete(
    "/{tool_id}",
    status_code=204,
    summary="Delete a tool",
)
async def delete_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    tool = await get_or_404(db, Tool, tool_id)
    await db.delete(tool)
    await db.commit()
