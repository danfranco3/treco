"""Deviation detection — emits real `deviation` events for the conditions
DeviationType names: stuck, token_spike, incomplete_criteria, process_exited.

Blocking deviations move the agent and ticket to `blocked`; warnings only
record the event. The watchdog loop runs for the server's lifetime and
catches agents that stop emitting events while still marked working.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.core.constants import AgentStatus, EventType, TicketStatus
from app.core.database import AsyncSessionLocal
from app.core.pubsub import agent_channel, agent_to_dict, bus, event_channel, event_to_dict
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL_SECONDS = 60.0


async def emit_deviation(
    agent_id: str,
    ticket_id: str,
    workspace_id: str,
    deviation_type: str,
    message: str,
    *,
    block: bool = True,
    context: dict[str, Any] | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        event = AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            ticket_id=ticket_id,
            workspace_id=workspace_id,
            event_type=EventType.DEVIATION,
            payload={
                "deviation_type": deviation_type,
                "severity": "error" if block else "warning",
                "message": message,
                "context": context or {},
            },
        )
        db.add(event)
        agent = await db.get(Agent, agent_id)
        if block:
            if agent:
                agent.status = AgentStatus.BLOCKED
                db.add(agent)
            ticket = await db.get(Ticket, ticket_id)
            if ticket and ticket.status != TicketStatus.DONE:
                ticket.status = TicketStatus.BLOCKED
                db.add(ticket)
        await db.commit()
        bus.publish(event_channel(workspace_id), event_to_dict(event))
        if block and agent:
            bus.publish(agent_channel(workspace_id), agent_to_dict(agent))


async def maybe_flag_token_spike(event: AgentEvent) -> None:
    """Flag a single event whose token total exceeds the ticket's rolling
    average by the configured multiplier. Warning only — no block."""
    total = event.tokens_in + event.tokens_out
    if total == 0:
        return
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.avg(AgentEvent.tokens_in + AgentEvent.tokens_out)).where(
                AgentEvent.ticket_id == event.ticket_id,
                AgentEvent.id != event.id,
                (AgentEvent.tokens_in + AgentEvent.tokens_out) > 0,
            )
        )
        avg = result.scalar()
    if avg and total > avg * settings.token_spike_multiplier:
        await emit_deviation(
            event.agent_id, event.ticket_id, event.workspace_id,
            "token_spike",
            f"Event consumed {total} tokens vs. rolling average {avg:.0f}",
            block=False,
            context={"tokens": total, "average": round(avg, 1)},
        )


async def flag_incomplete_criteria(agent_id: str, ticket_id: str, workspace_id: str) -> None:
    """Flag a finished run that left acceptance criteria unchecked. Warning only."""
    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        return
    remaining = [c["id"] for c in (ticket.acceptance_criteria or []) if not c.get("done")]
    if remaining:
        await emit_deviation(
            agent_id, ticket_id, workspace_id,
            "incomplete_criteria",
            f"Run finished with {len(remaining)} unchecked criteria",
            block=False,
            context={"criterion_ids": remaining},
        )


async def _check_stuck_agents() -> None:
    cutoff = datetime.utcnow() - timedelta(seconds=settings.stuck_after_seconds)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent).where(Agent.status == AgentStatus.WORKING))
        working = result.scalars().all()
        stuck: list[Agent] = []
        for agent in working:
            last = await db.execute(
                select(func.max(AgentEvent.created_at)).where(AgentEvent.agent_id == agent.id)
            )
            last_event_at = last.scalar()
            if last_event_at is not None and last_event_at < cutoff:
                stuck.append(agent)
    for agent in stuck:
        await emit_deviation(
            agent.id, agent.current_ticket_id or "", agent.workspace_id,
            "stuck",
            f"No events for over {settings.stuck_after_seconds}s while working",
            block=True,
        )


async def deviation_watchdog() -> None:
    """Server-lifetime loop. Blocked agents drop out of the working filter,
    so each stuck agent is flagged exactly once."""
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)
        try:
            await _check_stuck_agents()
        except Exception:
            logger.exception("Deviation watchdog pass failed")
