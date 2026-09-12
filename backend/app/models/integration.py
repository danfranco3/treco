import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ticket import AnyJSON


class Integration(Base):
    """External tracker sync config (Jira/Linear). Tokens never live here —
    config holds only base_url/project_key/field mappings; credential_ref is
    an opaque handle into the chmod-600 local credential store."""
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String)  # jira | linear

    config: Mapped[dict[str, Any]] = mapped_column(AnyJSON)
    credential_ref: Mapped[str] = mapped_column(String)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
