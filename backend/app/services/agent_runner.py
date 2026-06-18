import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AgentStatus, EventType
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.services.auth import generate_api_key

RUNS_DIR = Path.home() / ".treco" / "runs"

_PERMISSION_KEYWORDS = ("permission", "denied", "not permitted", "requires approval")


async def mint_agent(workspace_id: str, name: str, db: AsyncSession) -> tuple[Agent, str]:
    raw_key, key_hash = generate_api_key()

    agent = Agent(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=name,
        api_key_hash=key_hash,
        status=AgentStatus.IDLE,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent, raw_key


async def spawn_agent_run(
    agent: Agent, raw_key: str, ticket: Ticket, prompt: str, repo_path: str, db: AsyncSession
) -> None:
    run_dir = RUNS_DIR / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)

    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps({
        "api_key": raw_key,
        "base_url": settings.backend_url,
        "workspace_id": agent.workspace_id,
    }))
    config_path.chmod(0o600)

    session_path = run_dir / "session.json"
    session_path.write_text(json.dumps({"ticket_id": ticket.id}))

    resolved_repo = Path(repo_path).resolve()
    log_path = run_dir / "stdout.log"

    env = {
        **os.environ,
        "TRECO_API_KEY": raw_key,
        "TRECO_URL": settings.backend_url,
        "TRECO_CONFIG_FILE": str(config_path),
        "TRECO_SESSION_FILE": str(session_path),
    }

    with open(log_path, "w") as log_fh:
        proc = subprocess.Popen(
            ["claude", "-p", prompt, "--permission-mode", "acceptEdits"],
            cwd=str(resolved_repo),
            env=env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    agent.status = AgentStatus.WORKING
    agent.current_ticket_id = ticket.id
    agent.pid = proc.pid
    agent.last_seen_at = datetime.utcnow()
    db.add(agent)

    db.add(AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=ticket.id,
        workspace_id=agent.workspace_id,
        event_type=EventType.TICKET_STARTED,
        payload={"source": "ui_implement"},
    ))
    await db.commit()

    asyncio.create_task(_reap(agent.id, ticket.id, proc, log_path))


async def _reap(agent_id: str, ticket_id: str, proc: subprocess.Popen, log_path: Path) -> None:
    await asyncio.get_event_loop().run_in_executor(None, proc.wait)

    async with AsyncSessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if not agent or agent.current_ticket_id != ticket_id:
            return

        terminal = await db.execute(
            select(AgentEvent)
            .where(AgentEvent.agent_id == agent_id)
            .where(AgentEvent.ticket_id == ticket_id)
            .where(AgentEvent.event_type.in_([EventType.DONE, EventType.ERROR]))
        )
        if terminal.scalar_one_or_none():
            return

        tail = ""
        try:
            tail = log_path.read_text()[-2000:].lower()
        except Exception:
            pass
        deviation_type = "awaiting_approval" if any(k in tail for k in _PERMISSION_KEYWORDS) else "process_exited"

        agent.status = AgentStatus.ERROR
        agent.pid = None
        db.add(agent)
        db.add(AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            ticket_id=ticket_id,
            workspace_id=agent.workspace_id,
            event_type=EventType.DEVIATION,
            payload={
                "deviation_type": deviation_type,
                "severity": "error" if deviation_type == "process_exited" else "warning",
                "message": (
                    "Agent process exited without finishing"
                    if deviation_type == "process_exited"
                    else "Agent stopped — looks like it needs a permission it can't get headlessly"
                ),
                "context": {"exit_code": proc.returncode},
            },
        ))
        await db.commit()
