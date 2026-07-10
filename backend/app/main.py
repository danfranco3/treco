import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.api.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.logging_config import configure_logging
from app.core.request_id import RequestIDMiddleware

_DEV_JWT_SECRET = "dev-secret-change-in-production"
logger = logging.getLogger(__name__)

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


def _validate_jwt_secret() -> None:
    secret = settings.jwt_secret
    if secret == _DEV_JWT_SECRET:
        logger.warning("JWT_SECRET is the default dev value — set a strong secret before production")
        return
    if len(secret.encode()) < 32:
        raise RuntimeError(
            f"JWT_SECRET is {len(secret.encode())} bytes — must be >= 32 bytes for security"
        )


async def _seed_default_workspace() -> None:
    from app.models.workspace import Workspace
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace))
        if not result.scalars().first():
            db.add(Workspace(id=str(uuid.uuid4()), name="Default", repo_path=None))
            await db.commit()


async def _reap_working_agents() -> None:
    """Reset any agent stuck at 'working' from a previous server run.

    asyncio tasks are killed on process exit, so any agent that was mid-run
    when the server stopped will never call _finish_agent. Mark them error.
    """
    from app.models.agent import Agent
    from app.core.constants import AgentStatus
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agent).where(Agent.status.in_([AgentStatus.WORKING, AgentStatus.AWAITING_APPROVAL]))
        )
        stuck = result.scalars().all()
        for agent in stuck:
            agent.status = AgentStatus.ERROR
            agent.current_ticket_id = None
            db.add(agent)
        if stuck:
            await db.commit()
            logger.info("Reaped %d stuck agent(s) from previous run", len(stuck))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    _validate_jwt_secret()
    await init_db()
    await _seed_default_workspace()
    await _reap_working_agents()
    yield


_OPENAPI_TAGS = [
    {
        "name": "tickets",
        "description": (
            "Manage tickets from any source (Jira, Linear, Asana, GitHub Issues, or custom). "
            "Tickets are the unit of work agents act on. Body is immutable after import; "
            "acceptance criteria are derived by LLM on creation."
        ),
    },
    {
        "name": "agents",
        "description": (
            "Create and monitor agents. Each agent holds an API key (returned once on creation) "
            "used to authenticate SDK calls via the `X-Agent-Key` header."
        ),
    },
    {
        "name": "events",
        "description": (
            "Append-only event stream emitted by agents. Records token usage, criterion checks, "
            "PR links, and deviations. Cost is computed at read time from `tokens_in`/`tokens_out` sums."
        ),
    },
    {
        "name": "workspaces",
        "description": "Workspaces group agents and tickets. Each workspace maps to a git repository on disk.",
    },
    {
        "name": "init",
        "description": (
            "One-shot bootstrap: create a workspace + agent in a single call. "
            "Used by `treco init` CLI command."
        ),
    },
    {
        "name": "fs",
        "description": "Local filesystem browser for repo path selection. Localhost-only; rejects remote callers.",
    },
    {
        "name": "meta",
        "description": "Health check and service metadata.",
    },
]

app = FastAPI(
    title="Treco",
    version="0.1.0",
    description=(
        "**Treco** is an open source agent observability platform.\n\n"
        "Agents report progress on tickets in real time. "
        "Tracks acceptance criteria, token consumption, and per-ticket cost across any ticket source "
        "(Jira, Linear, Asana, GitHub Issues, or custom).\n\n"
        "## Authentication\n\n"
        "- **Agent SDK routes** (`/api/events`, agent self-lookup): `X-Agent-Key: <raw_key>` header — "
        "key is SHA-256 hashed and matched against `agent.api_key_hash`.\n"
        "- **Dashboard routes** (`/api/workspaces`, `/api/tickets`, etc.): no auth required in the "
        "default single-tenant deployment.\n\n"
        "## Key invariants\n\n"
        "- `Ticket.body` is immutable after import.\n"
        "- `agent_events` is append-only — no UPDATE or DELETE.\n"
        "- Cost is computed at read time from token sums, never persisted.\n"
        "- API keys are stored SHA-256 hashed and returned only once."
    ),
    contact={"name": "Treco", "url": "https://github.com/treco-dev/treco"},
    license_info={"name": "MIT"},
    openapi_tags=_OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router, prefix="/api")


@app.get(
    "/health",
    tags=["meta"],
    summary="Service health check",
    description="Returns `200 ok` when the API and database are reachable. Returns `503` when the database is unavailable.",
)
async def health() -> JSONResponse:
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    payload = {"status": "ok", "db": db_status, "version": app.version}
    status_code = 503 if db_status == "error" else 200
    return JSONResponse(content=payload, status_code=status_code)


_ui_dir = _find_ui_dir()

def _shell_response(section_dir: Path, item_id: str) -> FileResponse:
    """Serve pre-rendered page or fall back to shell for client-side routing."""
    exact = section_dir / item_id / "index.html"
    if exact.exists():
        return FileResponse(exact)
    shell = section_dir / "__shell__" / "index.html"
    if shell.exists():
        return FileResponse(shell)
    raise HTTPException(status_code=404)


if _ui_dir:
    # Explicit routes for dynamic segments so StaticFiles 404s don't swallow them.
    # These match before the mount and check for an exact pre-rendered file first,
    # falling back to the __shell__ HTML so the client-side router takes over.

    @app.get("/tickets/{ticket_id:path}", include_in_schema=False)
    async def _ticket_shell(ticket_id: str) -> FileResponse:
        return _shell_response(_ui_dir / "tickets", ticket_id)

    # Mount last — API routes take priority
    app.mount("/", StaticFiles(directory=_ui_dir, html=True), name="ui")
