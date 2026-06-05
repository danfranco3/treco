"""
Background worker — processes async jobs posted to the agent_events table.
Currently a no-op placeholder; the event API writes directly.
Extend here for: webhook fanout, Slack notifications, criteria re-evaluation.
"""
import asyncio
import logging

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_once() -> None:
    async with AsyncSessionLocal() as _db:
        pass  # reserved for future job processing


async def run_loop(interval: float = 5.0) -> None:
    logger.info("Worker started, polling every %.1fs", interval)
    while True:
        try:
            await run_once()
        except Exception:
            logger.exception("Worker iteration failed")
        await asyncio.sleep(interval)
