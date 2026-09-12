from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.models.integration import Integration
from app.services.sync.base import delete_credential, save_credential

router = APIRouter()


class CreateIntegrationRequest(BaseModel):
    workspace_id: str = Field(..., examples=["ws-abc123"])
    provider: Literal["jira", "linear"]
    config: dict[str, Any] = Field(
        default={},
        description="Provider config — base_url/email/status_map for Jira, status_map for Linear. Never the token.",
    )
    token: str = Field(..., description="API token. Stored in the chmod-600 local credential store, never in the database.")


class UpdateIntegrationRequest(BaseModel):
    config: dict[str, Any] | None = None
    enabled: bool | None = None
    token: str | None = Field(None, description="New token to rotate into the local credential store.")


class IntegrationResponse(BaseModel):
    id: str
    workspace_id: str
    provider: str
    config: dict[str, Any]
    enabled: bool
    last_sync_at: datetime | None
    last_sync_status: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "",
    response_model=IntegrationResponse,
    summary="Create a tracker integration",
    description="Link a Jira or Linear tracker to a workspace. The token goes to the local credential store only.",
)
async def create_integration(req: CreateIntegrationRequest, db: AsyncSession = Depends(get_db)):
    credential_ref = save_credential(req.token, req.provider)
    integration = Integration(
        workspace_id=req.workspace_id,
        provider=req.provider,
        config=req.config,
        credential_ref=credential_ref,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return integration


@router.get(
    "",
    response_model=list[IntegrationResponse],
    summary="List integrations in a workspace",
)
async def list_integrations(workspace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Integration).where(Integration.workspace_id == workspace_id))
    return result.scalars().all()


@router.get(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Get an integration",
)
async def get_integration(integration_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Integration, integration_id)


@router.patch(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Update an integration",
    description="Update config, toggle enabled, or rotate the stored token.",
)
async def update_integration(
    integration_id: str,
    req: UpdateIntegrationRequest,
    db: AsyncSession = Depends(get_db),
):
    integration = await get_or_404(db, Integration, integration_id)
    if req.config is not None:
        integration.config = req.config
    if req.enabled is not None:
        integration.enabled = req.enabled
    if req.token is not None:
        delete_credential(integration.credential_ref)
        integration.credential_ref = save_credential(req.token, integration.provider)
    await db.commit()
    await db.refresh(integration)
    return integration


@router.delete(
    "/{integration_id}",
    status_code=204,
    summary="Delete an integration",
    description="Remove the integration row and its token from the local credential store.",
)
async def delete_integration(integration_id: str, db: AsyncSession = Depends(get_db)):
    integration = await get_or_404(db, Integration, integration_id)
    delete_credential(integration.credential_ref)
    await db.delete(integration)
    await db.commit()
