import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

# JSONB on Postgres, JSON on SQLite
AnyJSON = JSONB().with_variant(JSON(), "sqlite")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # source: 'jira' | 'linear' | 'asana' | 'github' | 'custom'
    source: Mapped[str] = mapped_column(String, index=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # Normalized fields — always derived from body, never hand-edited
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")

    # Raw provider payload — never mutated after import
    body: Mapped[dict[str, Any]] = mapped_column(AnyJSON, default=dict)

    # LLM-extracted acceptance criteria: [{"id": str, "text": str, "done": bool}]
    acceptance_criteria: Mapped[list[dict[str, Any]]] = mapped_column(AnyJSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
