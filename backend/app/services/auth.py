import hashlib
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent


def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, key_hash)."""
    raw_key = settings.sdk_key_prefix + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def resolve_agent(api_key: str, db: AsyncSession) -> Agent:
    """Resolves agent by raw API key. Raises 401 if not found."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    result = await db.execute(select(Agent).where(Agent.api_key_hash == key_hash))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent API key")
    return agent
