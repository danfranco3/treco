# Treco

Real-time observability for AI coding agents. See which agents are working on which tickets, track acceptance criteria completion, and measure token spend per session.

Works with Claude Code out of the box. Any HTTP-capable agent (LangChain, CrewAI, AutoGen, custom) works via the Python SDK.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/danfranco3/treco)

![Treco dashboard — agent kanban, live event feed, criteria burndown](docs/dashboard.png)

---

## Quick start

### Option A — Docker (full stack, one command)

Requires Docker. Gives you the backend API + full dashboard.

```bash
git clone https://github.com/danfranco3/treco
cd treco
cp backend/.env.example backend/.env
docker compose up
```

Dashboard: http://localhost:3000 · API: http://localhost:8001

Then install the CLI and point it at your local instance:

```bash
pip install "treco[server]"
treco init  # enter http://localhost:8001 when prompted
treco import https://github.com/org/repo/issues/42
treco start
claude "implement the issue"
```

Seed demo data to see the dashboard with live-looking data:

```bash
pip install httpx
python backend/scripts/seed_demo.py
```

---

### Option B — pip install (full stack, no Docker)

Requires Python 3.11+. No Docker, no Node.js required at runtime. Runs backend + dashboard from a single port.

```bash
pip install "treco[server]"
treco server start        # backend + dashboard at http://localhost:8001
treco init                # registers agent, wires Claude Code hooks
treco import https://github.com/org/repo/issues/42
treco start
claude "implement the issue"
```

Dashboard: http://localhost:8001 · API docs: http://localhost:8001/docs

> **Note:** The pip package bundles a pre-built UI. To get the latest UI from source, run `make build-package` after cloning.

---

## What it shows

- **Agent board** — kanban of idle / working / error agents, live pulse animation while active
- **Live event stream** — terminal-style feed of everything agents are doing
- **Ticket detail** — acceptance criteria checklist with agent attribution and timestamp per criterion
- **Cost panel** — tokens in/out, estimated USD, per-model breakdown, per-event bar chart
- **Criteria burndown** — how many criteria complete over time

---

## Claude Code integration (manual)

If you already have a backend running:

### 1. Register an agent

```bash
curl -X POST http://localhost:8001/api/agents/ \
  -H "Content-Type: application/json" \
  -d '{"workspace_id": "my-workspace", "name": "my-agent"}'
# Returns: { "id": "...", "api_key": "treco_..." }
# Save the api_key — shown only once
```

### 2. Configure CLI

```bash
treco init
# enter URL and API key
```

Or set env vars:

```bash
export TRECO_API_KEY=treco_...
export TRECO_URL=http://localhost:8001
```

### 3. Wire hooks (one-time, handled automatically by `treco init`)

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": ".*", "hooks": [{ "type": "command", "command": "treco hook post-tool-use" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "treco hook stop" }] }
    ]
  }
}
```

### 4. Track a ticket

```bash
treco start <ticket-id>
# run claude normally — Treco captures token usage in the background
treco check <criterion-id>   # mark a criterion done
treco status                 # see current session state
```

---

## Python SDK

```python
from treco import TrecoClient

client = TrecoClient(api_key="treco_...", base_url="http://localhost:8001")

async with client.track("ticket-id"):
    result = await your_agent.run(ticket)
    await client.check("ticket-id", criterion_id="crit-uuid", tokens_in=1200, tokens_out=400)
    await client.log("ticket-id", "opened PR", payload={"url": "https://github.com/..."})
```

### LangChain

```python
from treco import TrecoClient

treco = TrecoClient(api_key="treco_...")

class TrecoCallback(BaseCallbackHandler):
    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id

    def on_llm_end(self, response, **kwargs):
        usage = response.llm_output.get("token_usage", {})
        asyncio.run(treco.log(self.ticket_id, "llm call", payload={}))
```

### CrewAI

```python
from treco import TrecoClient

treco = TrecoClient(api_key="treco_...")

@crew.task
async def my_task(ticket_id: str):
    await treco.start(ticket_id)
    result = await crew.kickoff()
    await treco.done(ticket_id)
    return result
```

---

## Import tickets

```bash
# From GitHub issue URL
treco import https://github.com/org/repo/issues/42

# From Linear issue URL
treco import https://linear.app/team/issue/ENG-123

# Via API
curl -X POST http://localhost:8001/api/tickets/fetch \
  -H "Content-Type: application/json" \
  -d '{"workspace_id": "my-workspace", "url": "https://github.com/org/repo/issues/42"}'
```

Acceptance criteria are extracted from the description via LLM on import (requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), or parsed from markdown checkboxes (`- [ ] criterion text`).

---

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `JWT_SECRET` | `dev-secret-change-in-production` | Change for any non-local deployment |
| `DATABASE_URL` | `sqlite+aiosqlite:///./treco.db` | Use asyncpg URL for Postgres |
| `DATABASE_MODE` | `sqlite` | `sqlite` or `postgres` |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | — | For LLM criteria extraction |
| `OPENAI_API_KEY` | — | Alternative LLM provider |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:8001"]` | Add your frontend origin |

---

## Database migrations

```bash
cd backend
alembic upgrade head      # apply migrations
alembic downgrade -1      # roll back one
```

---

## Development

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend && npm install && npm run dev

# Tests
cd backend && pytest tests/ -v
cd backend/sdk/python && pytest tests/ -v
```

---

## License

MIT
