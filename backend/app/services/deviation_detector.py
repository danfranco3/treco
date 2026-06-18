import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EventType
from app.models.agent import Agent
from app.models.event import AgentEvent


def _deviation_event(
    agent: Agent,
    ticket_id: str,
    deviation_type: str,
    severity: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> AgentEvent:
    return AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=ticket_id,
        workspace_id=agent.workspace_id,
        event_type=EventType.DEVIATION,
        payload={
            "deviation_type": deviation_type,
            "severity": severity,
            "message": message,
            "context": context or {},
        },
    )


async def check_post_event(
    event: AgentEvent,
    agent: Agent,
    db: AsyncSession,
) -> list[AgentEvent]:
    deviations: list[AgentEvent] = []

    if event.event_type == EventType.DONE:
        from app.models.ticket import Ticket
        result = await db.execute(select(Ticket).where(Ticket.id == event.ticket_id))
        ticket = result.scalar_one_or_none()
        if ticket and ticket.acceptance_criteria:
            unchecked = [c for c in ticket.acceptance_criteria if not c.get("done")]
            if unchecked:
                texts = [c.get("text", "") for c in unchecked[:3]]
                suffix = f" (+{len(unchecked) - 3} more)" if len(unchecked) > 3 else ""
                deviations.append(_deviation_event(
                    agent=agent,
                    ticket_id=event.ticket_id,
                    deviation_type="incomplete_criteria",
                    severity="error",
                    message=f"{len(unchecked)} criteria not completed: {texts}{suffix}",
                    context={"unchecked_ids": [c.get("id") for c in unchecked]},
                ))

    if event.event_type in (EventType.DONE, EventType.LOG, EventType.ERROR):
        event_tokens = event.tokens_in + event.tokens_out
        if event_tokens > 0:
            result = await db.execute(
                select(func.avg(AgentEvent.tokens_in + AgentEvent.tokens_out))
                .where(AgentEvent.ticket_id == event.ticket_id)
                .where(AgentEvent.event_type.notin_(["deviation", "heartbeat"]))
                .where(AgentEvent.id != event.id)
            )
            avg_tokens = result.scalar()

            # Need at least 5 prior data points for a meaningful baseline
            count_result = await db.execute(
                select(func.count(AgentEvent.id))
                .where(AgentEvent.ticket_id == event.ticket_id)
                .where(AgentEvent.event_type.notin_(["deviation", "heartbeat"]))
                .where(AgentEvent.id != event.id)
                .where(AgentEvent.tokens_in + AgentEvent.tokens_out > 0)
            )
            prior_count = count_result.scalar() or 0

            if avg_tokens and prior_count >= 5 and event_tokens > avg_tokens * 5:
                deviations.append(_deviation_event(
                    agent=agent,
                    ticket_id=event.ticket_id,
                    deviation_type="token_spike",
                    severity="warning",
                    message=f"Token spike: {event_tokens} tokens vs avg {int(avg_tokens)}",
                    context={"event_tokens": event_tokens, "avg_tokens": int(avg_tokens)},
                ))

    return deviations
