import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)

    # Hashed SDK API key
    api_key_hash: Mapped[str] = mapped_column(String, unique=True)

    status: Mapped[str] = mapped_column(String, default="idle")  # idle | working | awaiting_approval | error
    current_ticket_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # PID of the spawned subprocess while status == "working"
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
