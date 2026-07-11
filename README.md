# Treco

Real-time observability for AI coding agents.

See what your agents are doing, track acceptance criteria, measure token spend per ticket, and launch Claude Code directly from the dashboard. Works with Claude Code out of the box. Any HTTP-capable agent works via the Python SDK.

[![CI](https://github.com/danfranco3/treco/actions/workflows/ci.yml/badge.svg)](https://github.com/danfranco3/treco/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/treco)](https://pypi.org/project/treco/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

![Treco dashboard](docs/dashboard.png)

---

## What works today

| Feature | Status |
|---------|--------|
| CLI — `treco init / new / start / done / check / log / status` | ✅ |
| Dashboard — agent board, live event feed, ticket detail | ✅ |
| Launch Claude Code agent directly from ticket UI | ✅ |
| Real-time streaming of agent output (stream-json) | ✅ |
| Permission approval UI — pause and resume agent mid-run | ✅ |
| Acceptance criteria with file evidence and notes | ✅ |
| MCP server — agent marks criteria via tool-use (no bash required) | ✅ |
| Claude Code hooks — auto token capture, session start/stop | ✅ |
| Python SDK — `TrecoClient` with typed helpers for all event types | ✅ |
| SQLite (default) and PostgreSQL | ✅ |
| `treco server start` — pip-only, no Node or Docker required | ✅ |
| Agent heartbeat timeout (marks offline after 5 min silence) | ✅ |
| Multi-user / auth | ❌ Single-tenant, no login required |

---

## Quick start

### Option A — pip (recommended, no Docker or Node required)

```bash
pip install "treco[server]"
treco server start   # starts backend + opens dashboard at http://localhost:8001
treco init           # registers workspace and agent, wires Claude Code hooks
treco new "Fix the login bug"
claude "fix the login bug per the acceptance criteria"
treco done
```

The dashboard opens automatically in your browser. Agent events appear in real time.

### Option B — Docker (full stack with PostgreSQL)

```bash
git clone https://github.com/danfranco3/treco
cd treco
cp backend/.env.example backend/.env   # edit JWT_SECRET at minimum
docker compose up
```

Dashboard: `http://localhost:3000` · API: `http://localhost:8001`

Then install the CLI and point it at your instance:

```bash
pip install "treco[server]"
treco init    # enter http://localhost:8001 when prompted for the URL
```

### Option C — dev from source

```bash
git clone https://github.com/danfranco3/treco
cd treco

# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend (new terminal)
cd frontend && npm install && npm run dev
# Dashboard: http://localhost:3000

# SDK/CLI (editable install)
cd backend/sdk/python && pip install -e ".[server,dev]"
treco init
```

Seed the dashboard with realistic demo data:

```bash
cd backend && python scripts/seed_demo.py
```

---

## CLI reference

```
treco init                          Interactive setup — workspace, agent, Claude Code hooks
treco new [title]                   Create a ticket (prompts if no title given)
treco start [ticket-id]             Start tracking a ticket (shows picker if no id)
treco check <criterion-id>          Mark an acceptance criterion done
treco log   <message>               Log a message to the active ticket
treco done                          End session, mark ticket done
treco status                        Show active session info
treco inject [ticket-id]            Write ticket context into your agent config file

treco server start [--port N]       Start backend daemon + open dashboard in browser
treco server stop                   Stop the background server
treco server status                 Show whether server is running
treco server open                   Open dashboard in browser (if server already running)
```

---

## Python SDK

```python
from treco import TrecoClient

async with TrecoClient(api_key="treco_...", base_url="http://localhost:8001") as client:
    await client.ticket_started(ticket_id)
    await client.log(ticket_id, "Running tests", tokens_in=500, tokens_out=200)
    await client.criterion_checked(ticket_id, criterion_id="crit-uuid")
    await client.pr_opened(ticket_id, url="https://github.com/org/repo/pull/42")
    await client.done(ticket_id)
```

---

## Launching agents from the UI

Open any ticket and click **Implement**. Treco spawns a Claude Code subprocess against your workspace, streams output in real time, and surfaces any permission prompts directly in the dashboard so you can approve or deny without leaving the browser.

The agent marks acceptance criteria via an MCP server that Treco injects automatically — no bash commands needed.

---

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `JWT_SECRET` | `dev-secret-change-in-production` | Change for any non-local deployment |
| `DATABASE_URL` | `sqlite+aiosqlite:///./treco.db` | Use `postgresql+asyncpg://...` for Postgres |
| `DATABASE_MODE` | `sqlite` | `sqlite` or `postgres` |
| `ANTHROPIC_API_KEY` | — | Required to launch Claude Code agents from the UI |
| `OPENAI_API_KEY` | — | Alternative LLM provider |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:8001"]` | Add your frontend origin |

---

## Self-hosting

Full self-hosting guide (Railway, Render, Fly.io, bare VPS): [docs/deployment.md](docs/deployment.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributors must sign the [Contributor License Agreement](https://cla-assistant.io/danfranco3/treco) before a PR can be merged.

---

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).

Self-hosting is free. You may not offer Treco as a hosted or managed service without a separate commercial agreement. For commercial licensing inquiries, open an issue.
