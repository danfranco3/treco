# Import all models so SQLAlchemy discovers them during create_all
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket

__all__ = ["Agent", "AgentEvent", "Ticket"]
