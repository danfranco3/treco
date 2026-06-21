from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserWorkspace(Base):
    __tablename__ = "user_workspaces"
    __table_args__ = (
        Index("ix_user_workspaces_user_id", "user_id"),
        Index("ix_user_workspaces_workspace_id", "workspace_id"),
    )

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String)  # "owner" | "member"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
