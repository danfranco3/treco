import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx


class TrecoClient:
    """Minimal SDK for agents to report progress to Treco."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key or os.environ["TRECO_API_KEY"]
        self._base_url = (base_url or os.environ.get("TRECO_URL", "http://localhost:8001")).rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-Agent-Key": self._api_key},
            timeout=10.0,
        )

    async def heartbeat(self, ticket_id: str) -> None:
        await self._emit(ticket_id, "heartbeat")

    async def start(self, ticket_id: str) -> None:
        await self._emit(ticket_id, "ticket_started")

    async def check(self, ticket_id: str, criterion_id: str, tokens_in: int = 0, tokens_out: int = 0, model: str | None = None) -> None:
        await self._emit(ticket_id, "criterion_checked", criterion_id=criterion_id, tokens_in=tokens_in, tokens_out=tokens_out, model=model)

    async def fail_criterion(self, ticket_id: str, criterion_id: str, reason: str = "") -> None:
        await self._emit(ticket_id, "criterion_failed", criterion_id=criterion_id, payload={"reason": reason})

    async def log(self, ticket_id: str, message: str, payload: dict[str, Any] | None = None) -> None:
        await self._emit(ticket_id, "log", payload={"message": message, **(payload or {})})

    async def done(self, ticket_id: str, tokens_in: int = 0, tokens_out: int = 0) -> None:
        await self._emit(ticket_id, "done", tokens_in=tokens_in, tokens_out=tokens_out)

    async def error(self, ticket_id: str, message: str) -> None:
        await self._emit(ticket_id, "error", payload={"message": message})

    async def _emit(
        self,
        ticket_id: str,
        event_type: str,
        criterion_id: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        body = {
            "ticket_id": ticket_id,
            "event_type": event_type,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "payload": payload or {},
        }
        if criterion_id:
            body["criterion_id"] = criterion_id
        if model:
            body["model"] = model

        response = await self._http.post("/api/events/", json=body)
        response.raise_for_status()

    async def _heartbeat_loop(self, ticket_id: str) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self.heartbeat(ticket_id)
            except Exception:
                pass

    @asynccontextmanager
    async def track(self, ticket_id: str):
        """Context manager: auto start/done/error around agent work."""
        await self.start(ticket_id)
        hb_task = asyncio.create_task(self._heartbeat_loop(ticket_id))
        try:
            yield self
            await self.done(ticket_id)
        except Exception as exc:
            await self.error(ticket_id, str(exc))
            raise
        finally:
            hb_task.cancel()

    async def close(self) -> None:
        await self._http.aclose()
