"""In-process pub/sub fan-out for SSE streams.

Replaces per-tick DB polling: publishers push dicts at the same call sites
that write rows; each open SSE connection consumes its own asyncio.Queue.
Single-process only — matches the asyncio.create_task runner architecture.
"""
import asyncio
from collections import defaultdict
from typing import Any

from typing_extensions import Self


class Subscription:
    def __init__(self, bus: "EventBus", channel: str) -> None:
        self._bus = bus
        self._channel = channel
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def __enter__(self) -> Self:
        self._bus._subscribers[self._channel].add(self.queue)
        return self

    def __exit__(self, *exc: object) -> None:
        self._bus._subscribers[self._channel].discard(self.queue)

    async def get(self, timeout: float) -> dict[str, Any] | None:
        """Next message, or None on timeout (caller yields a keepalive)."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def publish(self, channel: str, data: dict[str, Any]) -> None:
        for queue in self._subscribers.get(channel, ()):
            queue.put_nowait(data)

    def subscribe(self, channel: str) -> Subscription:
        return Subscription(self, channel)


bus = EventBus()


def event_channel(workspace_id: str) -> str:
    return f"events:{workspace_id}"


def agent_channel(workspace_id: str) -> str:
    return f"agents:{workspace_id}"


def trace_channel(workspace_id: str) -> str:
    return f"traces:{workspace_id}"


def telemetry_channel(workspace_id: str) -> str:
    return f"telemetry:{workspace_id}"


def event_to_dict(event: Any) -> dict[str, Any]:
    return {
        "id": event.id,
        "agent_id": event.agent_id,
        "ticket_id": event.ticket_id,
        "workspace_id": event.workspace_id,
        "event_type": event.event_type,
        "criterion_id": event.criterion_id,
        "tokens_in": event.tokens_in,
        "tokens_out": event.tokens_out,
        "model": event.model,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }


def trace_to_dict(trace: Any) -> dict[str, Any]:
    return {
        "id": trace.id,
        "agent_id": trace.agent_id,
        "ticket_id": trace.ticket_id,
        "parent_trace_id": trace.parent_trace_id,
        "event_id": trace.event_id,
        "step_type": trace.step_type,
        "tool_name": trace.tool_name,
        "status": trace.status,
        "tokens_in": trace.tokens_in,
        "tokens_out": trace.tokens_out,
        "duration_ms": trace.duration_ms,
        "payload": trace.payload,
        "created_at": trace.created_at.isoformat(),
    }


def telemetry_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "ticket_id": row.ticket_id,
        "agent_id": row.agent_id,
        "metric": row.metric,
        "value": row.value,
        "unit": row.unit,
        "dims": row.dims,
        "created_at": row.created_at.isoformat(),
    }


def agent_to_dict(agent: Any) -> dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "status": agent.status,
        "current_ticket_id": agent.current_ticket_id,
        "workspace_id": agent.workspace_id,
    }
