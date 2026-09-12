import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ticket import AnyJSON


class Trace(Base):
    """Structured step index over an agent run. Additive to agent_events —
    never a replacement; agent_events stays the append-only source of truth."""
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String, index=True)
    ticket_id: Mapped[str] = mapped_column(String, index=True)
    parent_trace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # FK-by-convention to agent_events.id when this node maps 1:1 to an event
    event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    step_type: Mapped[str] = mapped_column(String, index=True)  # tool_call | llm_turn | test_run | criterion_check | permission_gate
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")  # running | ok | error | skipped

    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payload: Mapped[dict[str, Any]] = mapped_column(AnyJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
