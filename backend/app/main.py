import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db


def _find_ui_dir() -> Path | None:
    here = Path(__file__).parent  # app/
    candidates = [
        here.parent.parent / "_ui",           # pip: site-packages/treco/_backend/app/../../_ui = treco/_ui
        here.parent.parent / "frontend" / "out",  # dev: backend/app/../../frontend/out = repo/frontend/out
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

_STUCK_MINUTES = 5


async def _health_monitor() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=_STUCK_MINUTES)
            async with AsyncSessionLocal() as db:
                from app.models.agent import Agent
                from app.models.event import AgentEvent

                result = await db.execute(
                    select(Agent)
                    .where(Agent.status == "working")
                    .where(
                        (Agent.last_seen_at == None) | (Agent.last_seen_at < cutoff)  # noqa: E711
                    )
                )
                stuck_agents = result.scalars().all()

                for agent in stuck_agents:
                    # Don't spam — skip if we already emitted a stuck deviation recently
                    recent = await db.execute(
                        select(AgentEvent)
                        .where(AgentEvent.agent_id == agent.id)
                        .where(AgentEvent.event_type == "deviation")
                        .where(AgentEvent.created_at > cutoff)
                    )
                    if recent.scalar_one_or_none():
                        continue

                    minutes_silent = int(
                        (datetime.utcnow() - agent.last_seen_at).total_seconds() / 60
                    ) if agent.last_seen_at else _STUCK_MINUTES

                    db.add(AgentEvent(
                        id=str(uuid.uuid4()),
                        agent_id=agent.id,
                        ticket_id=agent.current_ticket_id or "",
                        workspace_id=agent.workspace_id,
                        event_type="deviation",
                        payload={
                            "deviation_type": "stuck",
                            "severity": "warning",
                            "message": f"Agent silent for {minutes_silent}+ minutes",
                            "context": {"minutes_silent": minutes_silent},
                        },
                    ))

                # Backstop for runs whose in-process reaper was lost (e.g. backend restarted)
                pid_result = await db.execute(
                    select(Agent).where(Agent.status == "working").where(Agent.pid.isnot(None))
                )
                for agent in pid_result.scalars().all():
                    try:
                        os.kill(agent.pid, 0)
                        continue  # still alive
                    except ProcessLookupError:
                        pass
                    except OSError:
                        continue

                    recent = await db.execute(
                        select(AgentEvent)
                        .where(AgentEvent.agent_id == agent.id)
                        .where(AgentEvent.event_type.in_(["deviation", "done", "error"]))
                        .where(AgentEvent.created_at > cutoff)
                    )
                    if recent.scalar_one_or_none():
                        continue

                    agent.status = "error"
                    agent.pid = None
                    db.add(agent)
                    db.add(AgentEvent(
                        id=str(uuid.uuid4()),
                        agent_id=agent.id,
                        ticket_id=agent.current_ticket_id or "",
                        workspace_id=agent.workspace_id,
                        event_type="deviation",
                        payload={
                            "deviation_type": "process_exited",
                            "severity": "error",
                            "message": "Agent process is no longer running",
                            "context": {},
                        },
                    ))

                await db.commit()
        except Exception:
            pass  # monitor must never crash


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    monitor = asyncio.create_task(_health_monitor())
    try:
        yield
    finally:
        monitor.cancel()


app = FastAPI(
    title="Treco",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


_ui_dir = _find_ui_dir()

if _ui_dir:
    # Explicit routes for dynamic segments so StaticFiles 404s don't swallow them.
    # These match before the mount and check for an exact pre-rendered file first,
    # falling back to the __shell__ HTML so the client-side router takes over.

    @app.get("/tickets/{ticket_id:path}", include_in_schema=False)
    async def _ticket_shell(ticket_id: str) -> FileResponse:
        exact = _ui_dir / "tickets" / ticket_id / "index.html"
        if exact.exists():
            return FileResponse(exact)
        shell = _ui_dir / "tickets" / "__shell__" / "index.html"
        if shell.exists():
            return FileResponse(shell)
        raise HTTPException(status_code=404)

    @app.get("/agents/{agent_id:path}", include_in_schema=False)
    async def _agent_shell(agent_id: str) -> FileResponse:
        exact = _ui_dir / "agents" / agent_id / "index.html"
        if exact.exists():
            return FileResponse(exact)
        shell = _ui_dir / "agents" / "__shell__" / "index.html"
        if shell.exists():
            return FileResponse(shell)
        raise HTTPException(status_code=404)

    # Mount last — API routes take priority
    app.mount("/", StaticFiles(directory=_ui_dir, html=True), name="ui")
