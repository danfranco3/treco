"""
Demo seeder — populates Treco with realistic agent activity so the UI
has something to show immediately.

Usage (from backend/):
  python scripts/seed_demo.py [--url http://localhost:8001] [--workspace demo]
"""

import argparse
import asyncio
import random
import sys
import uuid
from pathlib import Path

# Allow importing backend modules when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, init_db
from app.models.user import User
from app.models.user_workspace import UserWorkspace
from app.models.workspace import Workspace
from app.services.auth import create_jwt

TICKETS = [
    {
        "title": "Implement OAuth2 login with GitHub",
        "description": """
Users should be able to sign in with their GitHub account.

- [ ] Register OAuth app in GitHub developer settings
- [ ] Add /auth/github/callback endpoint
- [ ] Store user profile (id, login, avatar_url) on first login
- [ ] Issue JWT on successful auth
- [ ] Handle token expiry and refresh
        """,
        "source": "github",
        "source_id": "42",
    },
    {
        "title": "Add rate limiting to public API endpoints",
        "description": """
Prevent abuse on unauthenticated endpoints.

- [ ] Add Redis-backed rate limiter middleware
- [ ] 100 req/min per IP on /api/events
- [ ] 20 req/min per IP on /api/tickets import
- [ ] Return 429 with Retry-After header
- [ ] Log rate limit hits to monitoring
        """,
        "source": "linear",
        "source_id": "ENG-88",
    },
    {
        "title": "Ticket detail page — criteria attribution",
        "description": """
When an agent checks a criterion, show which agent did it and when.

- [ ] Join criterion_checked events to acceptance_criteria by criterion_id
- [ ] Show agent name pill next to each done criterion
- [ ] Show relative timestamp (e.g. '3m ago')
- [ ] Handle case where agent is deleted after event
        """,
        "source": "jira",
        "source_id": "TRECO-14",
    },
    {
        "title": "Export ticket progress as CSV",
        "description": """
Teams want to export per-ticket metrics to share in standups.

- [ ] GET /api/tickets/export?workspace_id=x returns CSV
- [ ] Columns: ticket_id, title, criteria_total, criteria_done, tokens_in, tokens_out, est_cost, last_agent
- [ ] Trigger download from frontend
        """,
        "source": "custom",
        "source_id": None,
    },
    {
        "title": "WebSocket / SSE real-time event stream",
        "description": """
Replace SWR polling with server-sent events for lower latency.

- [ ] Add GET /api/events/stream?workspace_id=x SSE endpoint
- [ ] Stream new AgentEvents as they are inserted
- [ ] Replace useTicketEvents SWR hook with useEventStream hook
- [ ] Graceful reconnect on connection drop
- [ ] Fallback to polling if SSE not supported
        """,
        "source": "github",
        "source_id": "61",
    },
]

AGENTS = ["aurora", "beacon", "cipher"]

MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "gpt-4o-mini"]

LOG_MESSAGES = [
    "Reading codebase structure",
    "Analyzing existing auth middleware",
    "Writing unit tests",
    "Running test suite",
    "Refactoring for clarity",
    "Checking edge cases",
    "Updating documentation",
    "Opening pull request",
    "Addressing review feedback",
]

# Stable ID so re-runs don't create duplicate seed users
_SEED_USER_ID = "00000000-seed-demo-user-000000000000"
_SEED_GITHUB_ID = "seed-demo-0"


async def _bootstrap(workspace_id: str) -> str:
    """Creates demo user + workspace + membership directly in DB. Returns JWT."""
    await init_db()
    async with AsyncSessionLocal() as db:
        user = await db.get(User, _SEED_USER_ID)
        if user is None:
            user = User(
                id=_SEED_USER_ID,
                github_id=_SEED_GITHUB_ID,
                login="demo-seed",
                avatar_url=None,
            )
            db.add(user)
            await db.flush()

        workspace = await db.get(Workspace, workspace_id)
        if workspace is None:
            workspace = Workspace(id=workspace_id, name="Demo Workspace", repo_path=None)
            db.add(workspace)
            await db.flush()

        result = await db.execute(
            select(UserWorkspace).where(
                UserWorkspace.user_id == _SEED_USER_ID,
                UserWorkspace.workspace_id == workspace_id,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(UserWorkspace(
                user_id=_SEED_USER_ID,
                workspace_id=workspace_id,
                role="owner",
            ))

        await db.commit()

    return create_jwt(_SEED_USER_ID)


class Seeder:
    def __init__(self, base_url: str, workspace_id: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.auth_headers = {"Authorization": f"Bearer {token}"}
        self.agent_keys: dict[str, str] = {}
        self.ticket_ids: list[str] = []

    async def run(self):
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            self.client = client
            print("Creating agents...")
            for name in AGENTS:
                await self._create_agent(name)

            print("Creating tickets...")
            for t in TICKETS:
                await self._create_ticket(t)

            print("Simulating agent activity...")
            await self._simulate_activity()

        print(f"\nSeeded {len(self.agent_keys)} agents and {len(self.ticket_ids)} tickets.")
        print(f"Open http://localhost:3000 — workspace: {self.workspace_id}")

    async def _create_agent(self, name: str):
        r = await self.client.post(
            "/api/agents",
            json={"workspace_id": self.workspace_id, "name": name},
            headers=self.auth_headers,
        )
        if r.status_code == 409:
            print(f"  agent '{name}' already exists, skipping")
            return
        r.raise_for_status()
        data = r.json()
        self.agent_keys[name] = data["api_key"]
        print(f"  agent '{name}' → key {data['api_key'][:20]}...")

    async def _create_ticket(self, spec: dict):
        source = spec["source"]
        sid = spec["source_id"] or ""

        if source != "custom":
            if source == "jira":
                raw: dict = {
                    "key": sid,
                    "fields": {
                        "summary": spec["title"],
                        "description": spec["description"],
                        "status": {"name": "In Progress"},
                    },
                }
            elif source == "linear":
                raw = {
                    "identifier": sid,
                    "title": spec["title"],
                    "description": spec["description"],
                    "state": {"name": "In Progress"},
                }
            else:  # github
                raw = {
                    "number": int(sid) if sid.isdigit() else 0,
                    "title": spec["title"],
                    "state": "open",
                    "body": spec["description"],
                }
            r = await self.client.post(
                "/api/tickets/import",
                json={"source": source, "workspace_id": self.workspace_id, "raw": raw},
                headers=self.auth_headers,
            )
        else:
            r = await self.client.post(
                "/api/tickets",
                json={
                    "workspace_id": self.workspace_id,
                    "title": spec["title"],
                    "description": spec["description"],
                },
                headers=self.auth_headers,
            )

        r.raise_for_status()
        ticket_id = r.json()["id"]
        self.ticket_ids.append(ticket_id)
        print(f"  ticket '{spec['title'][:40]}...' → {ticket_id}")

    async def _simulate_activity(self):
        agent_names = list(self.agent_keys.keys())
        if not agent_names:
            print("  no agents available — skipping activity simulation")
            return

        for i, ticket_id in enumerate(self.ticket_ids):
            agent_name = agent_names[i % len(agent_names)]
            api_key = self.agent_keys[agent_name]
            await self._run_agent_on_ticket(api_key, ticket_id, complete=(i < 3))

    async def _run_agent_on_ticket(self, api_key: str, ticket_id: str, complete: bool):
        headers = {"X-Agent-Key": api_key}

        r = await self.client.get(f"/api/tickets/{ticket_id}")
        r.raise_for_status()
        ticket = r.json()
        criteria = ticket.get("acceptance_criteria", [])

        async def emit(event_type: str, **kwargs):
            body = {
                "ticket_id": ticket_id,
                "event_type": event_type,
                "tokens_in": 0,
                "tokens_out": 0,
                "payload": {},
                **kwargs,
            }
            r2 = await self.client.post("/api/events", json=body, headers=headers)
            r2.raise_for_status()

        await emit("ticket_started", payload={"message": "Starting work on ticket"})

        model = random.choice(MODELS)
        total_in, total_out = 0, 0

        for j, criterion in enumerate(criteria):
            for _ in range(random.randint(1, 3)):
                ti = random.randint(800, 4000)
                to = random.randint(200, 1200)
                total_in += ti
                total_out += to
                await emit(
                    "log",
                    tokens_in=ti,
                    tokens_out=to,
                    model=model,
                    payload={"message": random.choice(LOG_MESSAGES)},
                )

            if complete or j < len(criteria) // 2:
                ti = random.randint(1000, 3000)
                to = random.randint(400, 1500)
                total_in += ti
                total_out += to
                await emit(
                    "criterion_checked",
                    criterion_id=criterion["id"],
                    tokens_in=ti,
                    tokens_out=to,
                    model=model,
                )
            elif j == len(criteria) // 2:
                await emit(
                    "criterion_failed",
                    criterion_id=criterion["id"],
                    payload={"reason": "Test assertion failed — needs investigation"},
                )

        if complete:
            await emit(
                "pr_opened",
                payload={
                    "message": "Opened pull request",
                    "url": "https://github.com/example/treco/pull/" + str(random.randint(10, 99)),
                },
            )
            await emit("done", tokens_in=total_in, tokens_out=total_out)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8001")
    parser.add_argument("--workspace", default="demo")
    args = parser.parse_args()

    print("Bootstrapping demo user + workspace in DB...")
    token = await _bootstrap(args.workspace)

    await Seeder(args.url, args.workspace, token).run()


if __name__ == "__main__":
    asyncio.run(main())
