# Treco

Real-time agent observability. See which agents are working on which tickets,
track acceptance criteria completion, and measure token consumption per ticket.

Works with Claude Code, LangChain, CrewAI, AutoGen, or any HTTP-capable agent.

![Dashboard: agent kanban, live event feed, criteria burndown]

## What it shows

- **Agent board** — kanban of idle / working / error agents, live pulse animation while active
- **Live event stream** — terminal-style feed of everything agents are doing
- **Ticket detail** — acceptance criteria checklist with agent attribution and timestamp per criterion
- **Cost panel** — tokens in/out, estimated USD, per-model breakdown, per-event bar chart
- **Criteria burndown** — how many criteria are getting completed over time

## Quick start (local)

```bash
git clone https://github.com/yourname/treco
cd treco
cp backend/.env.example backend/.env
# edit backend/.env — set JWT_SECRET and optionally ANTHROPIC_API_KEY

docker compose up
```

Frontend at http://localhost:3000 · Backend at http://localhost:8000

Seed demo data so the UI has something to show:

```bash
pip install httpx
python backend/scripts/seed_demo.py
```

## Claude Code integration

### 1. Install the SDK

```bash
pip install treco
```

### 2. Configure

```bash
treco init
# enter your Treco URL and agent API key
```

Or set env vars:

```bash
export TRECO_API_KEY=treco_...
export TRECO_URL=http://localhost:8000
```

### 3. Wire up hooks (one time)

Add to `.claude/settings.json` in your project (or `~/.claude/settings.json` globally):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [{ "type": "command", "command": "treco hook post-tool-use" }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "treco hook stop" }]
      }
    ]
  }
}
```

### 4. Track a ticket

Before starting a Claude Code session:

```bash
treco start <ticket-id>
```

Claude Code runs normally. Treco captures every tool call's token usage in the
background. When Claude Code exits, Treco posts the final `done` event with totals.

Mark acceptance criteria from inside the session:

```bash
treco check <criterion-id>
treco fail  <criterion-id>
treco log   "opened PR #42"
```

Check the current session:

```bash
treco status
```

## Python SDK (any agent framework)

```python
from treco import TrecoClient

client = TrecoClient(api_key="treco_...", base_url="http://localhost:8000")

# Context manager: auto start/done/error
async with client.track("ticket-id"):
    result = await your_agent.run(ticket)
    await client.check("ticket-id", criterion_id="crit-uuid", tokens_in=1200, tokens_out=400)
    await client.log("ticket-id", "opened PR", payload={"url": "https://github.com/..."})
```

### LangChain callback

```python
from treco import TrecoClient

treco = TrecoClient(api_key="treco_...")

class TrecoCallback(BaseCallbackHandler):
    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id

    def on_llm_end(self, response, **kwargs):
        usage = response.llm_output.get("token_usage", {})
        asyncio.run(treco.log(
            self.ticket_id, "llm call",
            payload={},
        ))
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

## Create an agent via API

```bash
curl -X POST http://localhost:8000/api/agents/ \
  -H "Content-Type: application/json" \
  -d '{"workspace_id": "my-workspace", "name": "my-agent"}'
# Returns: { "id": "...", "api_key": "treco_..." }
# Save the api_key — it is only shown once
```

## Import tickets

```bash
# From Jira
curl -X POST http://localhost:8000/api/tickets/import \
  -H "Content-Type: application/json" \
  -d '{"source": "jira", "workspace_id": "my-workspace", "raw": <jira issue JSON>}'

# From GitHub
curl -X POST http://localhost:8000/api/tickets/import \
  -d '{"source": "github", "workspace_id": "my-workspace", "raw": <issue JSON>}'

# Custom
curl -X POST http://localhost:8000/api/tickets/ \
  -d '{"workspace_id": "my-workspace", "title": "...", "description": "...", "acceptance_criteria": ["criterion 1", "criterion 2"]}'
```

Acceptance criteria are extracted from `description` via LLM on import
(if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set) or parsed from markdown
checkboxes (`- [ ] criterion`).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./treco.db` | Database connection string |
| `DATABASE_MODE` | `sqlite` | `sqlite` or `postgres` |
| `JWT_SECRET` | required | Secret for JWT signing |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | — | For criteria extraction |
| `OPENAI_API_KEY` | — | Alternative LLM provider |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins |

## Self-hosting

```bash
# Postgres mode
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/treco
DATABASE_MODE=postgres
```

The Docker Compose file includes Postgres. SQLite is default for zero-infra local use.

## License

MIT
