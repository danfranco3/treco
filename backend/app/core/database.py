from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

T = TypeVar("T")

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    import app.models  # noqa: F401 — registers all models with Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_or_404(db: AsyncSession, model: type[T], pk: str, detail: str | None = None) -> T:
    obj = await db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail=detail or f"{model.__name__} not found")
    return obj  # type: ignore[return-value]
