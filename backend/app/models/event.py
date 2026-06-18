import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

AnyJSON = JSONB().with_variant(JSON(), "sqlite")


class AgentEvent(Base):
    """Append-only event stream. No updates, no deletes."""
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String, index=True)
    ticket_id: Mapped[str] = mapped_column(String, index=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)

    # ticket_started | criterion_checked | criterion_failed | pr_opened | done | error | log | heartbeat | deviation
    event_type: Mapped[str] = mapped_column(String, index=True)

    # For criterion events
    criterion_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Token consumption for this event
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String, nullable=True)

    # Free-form payload (log message, PR URL, error details, etc.)
    payload: Mapped[dict[str, Any]] = mapped_column(AnyJSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
