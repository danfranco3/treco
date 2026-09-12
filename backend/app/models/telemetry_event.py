import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ticket import AnyJSON


class TelemetryEvent(Base):
    """Pre-aggregated metric rows — dashboards read these instead of
    re-scanning agent_events/traces on every paint."""
    __tablename__ = "telemetry_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    ticket_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    metric: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)  # tokens | usd | ms | count | ratio

    dims: Mapped[dict[str, Any]] = mapped_column(AnyJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
