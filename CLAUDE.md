# Treco — Codebase Reference

## What It Is

Open source agent observability platform. Agents report progress on tickets in real time.
Tracks acceptance criteria, token consumption, and per-ticket cost across any ticket source
(Jira, Linear, Asana, GitHub Issues, or custom).

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.11+), SQLAlchemy async, PostgreSQL + JSONB / SQLite |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind |
| Agent SDK | Python (`backend/sdk/python/`) — published to PyPI as `treco` |
| CLI | `treco` CLI — entrypoint `backend/sdk/python/treco/cli.py` |
| LLM | Anthropic (`claude-haiku-4-5-20251001`) or OpenAI (`gpt-4o-mini`) for criteria extraction |
| Auth | JWT (HS256, `JWT_SECRET` required env var) + SHA-256 hashed SDK keys (`X-Agent-Key` header) |
| DB | `AnyJSON` type alias: JSONB on Postgres, JSON on SQLite — defined in `models/ticket.py` and `models/event.py` |

---

## Repo Layout

```
backend/
  app/
    main.py                   # FastAPI app factory, CORS, lifespan
    api/
      router.py               # Mounts all route modules under /api
      routes/
        tickets.py            # CRUD + fetch/import/bulk import
        agents.py             # Create agent, resolve by X-Agent-Key
        events.py             # Append-only event stream + cost aggregation
        init.py               # One-shot workspace+agent bootstrap
    core/
      config.py               # Pydantic Settings — all env vars here
      database.py             # Async engine, session factory, Base, init_db
    models/
      ticket.py               # Ticket — body immutable, criteria derived
      agent.py                # Agent — api_key_hash, never raw key
      event.py                # AgentEvent — append-only
    services/
      adapters/
        base.py               # TicketAdapter ABC + NormalizedTicket schema
        jira.py
        linear.py
      criteria_extractor/
        __init__.py           # LLM extraction + markdown checkbox fallback
    worker/
      runner.py               # Event processor
      main.py                 # Worker entry point
  sdk/python/
    treco/
      client.py               # TrecoClient — async httpx, context manager
      cli.py                  # Full CLI: init/new/start/check/done/inject/server/hook
      server.py               # Daemon server management
    tests/                    # pytest + respx
  tests/                      # Backend integration tests
  requirements.txt
  Dockerfile

frontend/
  app/                        # Next.js App Router
  components/
  lib/api.ts                  # All backend calls

backend/.env                  # Local env (gitignored — never commit)
```

---

## Dev Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Seed demo data
python scripts/seed_demo.py

# SDK / CLI (from repo root or sdk dir)
cd backend/sdk/python
pip install -e ".[server,dev]"
treco init

# Tests
cd backend
pytest tests/

cd backend/sdk/python
pytest tests/

# Frontend
cd frontend
npm install
npm run dev        # localhost:3000
npm run build      # must pass before merging
npm run lint
npx tsc --noEmit   # type-check
```

---

## Environment Variables

All declared in `backend/app/core/config.py` via Pydantic Settings.

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `JWT_SECRET` | **yes** | — | Never log, never expose |
| `DATABASE_URL` | no | `sqlite+aiosqlite:///./treco.db` | Use asyncpg URL for Postgres |
| `DATABASE_MODE` | no | `sqlite` | `sqlite` or `postgres` |
| `ANTHROPIC_API_KEY` | no | — | Needed for LLM criteria extraction |
| `OPENAI_API_KEY` | no | — | Alternative LLM provider |
| `LLM_PROVIDER` | no | `anthropic` | `anthropic` or `openai` |
| `CORS_ORIGINS` | no | `["http://localhost:3000"]` | JSON list |

SDK / CLI reads from `~/.treco/config.json` or `TRECO_API_KEY` / `TRECO_URL` env vars.

---

## Key Invariants — Never Violate

- **`Ticket.body` is immutable.** Raw provider JSON. Never mutate after import.
- **Normalized fields are derived.** `title`, `description`, `acceptance_criteria` come from `body` via adapter/LLM. Never hand-set from arbitrary user input.
- **`agent_events` is append-only.** No UPDATE, no DELETE on that table. Ever.
- **Cost is computed at read time.** `SUM(tokens_in)` / `SUM(tokens_out)` per ticket from events. Never persist a derived cost value.
- **API key is stored hashed.** `Agent.api_key_hash` = SHA-256. Raw key returned once on creation, never again. Never log it, never include in error messages.
- **Workspace isolation.** All queries filter by `workspace_id`. Cross-tenant data leakage is a critical bug.

---

## Security Rules

### Authentication
- Agent requests authenticate via `X-Agent-Key` header → SHA-256 hash lookup.
- `_resolve_agent()` in `events.py` is the canonical pattern — copy it exactly when adding new authenticated routes.
- JWT secret must be at least 32 random bytes. Validate on startup if adding auth middleware.
- Tokens (GitHub PAT, Linear API key) stored in `~/.treco/config.json` (chmod 600). Never log them. Never include in HTTP error responses.

### Input Validation
- All HTTP request bodies go through Pydantic models. No raw `dict` from `request.body()`.
- `workspace_id` is always validated as a non-empty string before DB queries — it's the only tenant boundary.
- `source` field on tickets uses `Literal["jira", "linear", "asana", "github", "custom"]` — reject unknowns.
- `event_type` uses a `Literal` union — reject unknowns at the Pydantic boundary.

### Injection
- All DB queries use SQLAlchemy ORM or parameterized `select()`. No string-interpolated SQL. Ever.
- The Linear bulk import builds a GraphQL query with `req.team_key` interpolated — **this is a known injection risk**. Any future work touching `tickets.py:226` must use GraphQL variables, not f-string interpolation.
- Ticket `body` and `payload` fields are JSONB — sanitize before rendering in frontend (XSS via ticket content is real).

### Secrets in Code
- `.env` is gitignored. `backend/.env` contains real secrets locally.
- Never add API keys, tokens, or `JWT_SECRET` to any committed file.
- `CONFIG_FILE` (`~/.treco/config.json`) is chmod 600 — verify this is set in `save_config()` on any config write.

---

## Performance Rules

### Database
- Use `select()` with explicit `.where()` filters — never load all rows then filter in Python.
- `workspace_id`, `agent_id`, `ticket_id`, `event_type`, `created_at` are all indexed. Use them.
- Cost aggregation (`get_ticket_cost`) uses `func.sum()` in SQL — keep it there.
- Avoid N+1: if listing tickets with their event counts, use a subquery or window function.
- `expire_on_commit=False` on sessions — objects stay usable after commit without extra round-trips.

### Async
- All DB calls are async (`await db.execute(...)`, `await db.get(...)`). Never block the event loop with sync I/O.
- `httpx.AsyncClient` for all outbound HTTP in routes. Use context manager or shared instance — don't create per-request clients in hot paths.
- `TrecoClient` in the SDK reuses one `httpx.AsyncClient` instance per client lifetime.

### LLM
- Criteria extraction (`extract_criteria`) is called only on ticket creation/import, never on reads.
- Model: `claude-haiku-4-5-20251001` (fast, cheap). Do not upgrade to Sonnet/Opus for extraction without measuring.
- If extraction fails (JSON parse error, network), fall back to `_parse_checkboxes` — never block ticket creation.

---

## Code Quality Rules

### No Dead Code
- No commented-out blocks. No TODO/FIXME left in PRs. No unused imports.
- `noqa: F401` is only acceptable in `database.py:init_db` (model registration side effect).

### Types
- All Python: fully typed. No `Any` unless it's a JSONB field (which is genuinely `dict[str, Any]`).
- All TypeScript: no `any`. Types live close to usage; no God-type files.
- Return types on all route handlers. Pydantic response models on all `@router.X` decorators.

### Functions
- One thing. Name is self-documenting.
- `_resolve_agent`, `_upsert_ticket`, `_build_criteria_block` are good examples of private helpers — keep that pattern.
- Max ~40 lines per function before extracting. Routes especially.

### Comments
- Default: none. Write a comment only when the WHY is non-obvious.
- `# JSONB on Postgres, JSON on SQLite` is a good example — documents a constraint.
- `# returned only on creation, never again` on `CreateAgentResponse.api_key` is another.
- Never write what the code does. Never reference issue numbers or callers.

### Error Handling
- Raise `HTTPException` at route boundaries with specific status codes.
- Never swallow exceptions silently. `_safe_hook` in CLI is the only sanctioned exception suppressor (hooks must not crash the agent's shell).
- Validate external inputs (HTTP bodies, provider API responses) at the boundary. Trust internal invariants.

---

## Testing Standards

- Backend tests: `backend/tests/` — pytest + `pytest-asyncio`.
- SDK tests: `backend/sdk/python/tests/` — pytest + `respx` for HTTP mocking.
- Test names describe behavior: `test_jira_adapter_normalizes_missing_description`.
- Every adapter (`jira.py`, `linear.py`, etc.) has integration tests in `backend/tests/test_adapters.py`.
- Every new route needs at least: happy path, 404 case, auth rejection (401).
- No mocks that diverge from real behavior. If you mock the DB, mark the test clearly and explain why.

---

## Adding a New Ticket Source

1. Create `backend/app/services/adapters/<source>.py` implementing `TicketAdapter`.
2. Register in `backend/app/services/adapters/__init__.py` `ADAPTERS` dict.
3. Add `source` literal to `ImportTicketRequest` in `tickets.py`.
4. Add tests in `backend/tests/test_adapters.py`.
5. Update `BulkImportRequest.source` literal if bulk import is supported.

## Adding a New Event Type

1. Add the literal to `EventRequest.event_type` in `events.py`.
2. Handle side effects in `post_event()` (agent status updates, ticket mutations).
3. Update `AgentEvent` model docstring comment.
4. Update SDK `TrecoClient` with a typed method if agents need to emit it.

## Adding a New Route Module

1. Create `backend/app/api/routes/<name>.py`.
2. Mount in `backend/app/api/router.py`.
3. All routes require Pydantic request/response models.
4. Any route accessing agent-scoped data must call `_resolve_agent()` first.

---

## Active Treco Ticket
**[42] Implement OAuth2 login with GitHub**  
Session: `treco status` | Done: `treco done` | Check: `treco check <id>`

Acceptance criteria:
- [ ] Register OAuth app in GitHub developer settings  <!-- id: 3f1ab0a1-318c-423f-88a7-a7c88703f93a -->
- [ ] Add /auth/github/callback endpoint  <!-- id: 4f0a15d7-f9a5-4f7e-a49e-07d9190c4b5e -->
- [ ] Store user profile (id, login, avatar_url) on first login  <!-- id: f616d7d6-4cf0-4ddf-88a3-d43d8b0906d8 -->
- [ ] Issue JWT on successful auth  <!-- id: 327b23b6-4e0b-44bc-9498-6023974a5df6 -->
- [ ] Handle token expiry and refresh  <!-- id: 6b06dd9d-86b3-4f1a-90a3-15c13e78e000 -->
