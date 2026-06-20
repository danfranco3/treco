# Import all models so SQLAlchemy discovers them during create_all
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.models.user import User
from app.models.workspace import Workspace

__all__ = ["Agent", "AgentEvent", "Ticket", "User", "Workspace"]
