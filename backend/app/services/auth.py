import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.models.user_workspace import UserWorkspace


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


def create_jwt(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_jwt(token: str) -> str:
    """Decodes JWT and returns user_id (sub). Raises 401 on invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload["sub"]
        return user_id
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    user_id = decode_jwt(authorization.removeprefix("Bearer "))
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def check_workspace_member(
    user_id: str,
    workspace_id: str,
    db: AsyncSession,
) -> UserWorkspace:
    """Returns membership row or raises 403 if user is not a member."""
    result = await db.execute(
        select(UserWorkspace).where(
            UserWorkspace.user_id == user_id,
            UserWorkspace.workspace_id == workspace_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    return membership
