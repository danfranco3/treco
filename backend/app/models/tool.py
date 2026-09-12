import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ticket import AnyJSON


class Tool(Base):
    """Registry of agent tools — local or community-imported."""
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)  # openapi | python | javascript
    source: Mapped[str] = mapped_column(String, default="local")  # local | community

    # Same shape as implement.py's _TOOLS entries: name/description/input_schema, plus entrypoint
    definition: Mapped[dict[str, Any]] = mapped_column(AnyJSON)

    safety_flag: Mapped[str] = mapped_column(String, default="unverified")  # verified | unverified | high_risk_network | high_risk_fs
    checksum: Mapped[str] = mapped_column(String)  # sha256 of definition, tamper detection on community imports

    installed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
