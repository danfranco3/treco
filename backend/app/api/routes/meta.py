from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class TierResponse(BaseModel):
    tier: Literal["free", "pro", "team"]
    max_parallel_agents: int


@router.get(
    "/tier",
    response_model=TierResponse,
    summary="Active tier and concurrency limit",
    description="Read-only view of the software tier boundaries — the frontend disables gated affordances from this.",
)
async def get_tier() -> TierResponse:
    return TierResponse(tier=settings.tier, max_parallel_agents=settings.max_parallel_agents)
