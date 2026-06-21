# Contributing to Treco

Treco is open source. This guide covers everything you need to go from clone to merged PR.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Git

---

## Dev Setup

### 1 — Clone and install backend

```bash
git clone https://github.com/your-org/treco
cd treco

cd backend
pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp backend/.env.example backend/.env  # if it exists, or create manually
```

Minimum required to run the backend and tests:

```bash
# backend/.env
JWT_SECRET=dev-secret-minimum-32-bytes-long-pad
```

For LLM criteria extraction (optional in dev):

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

See [self-hosting.md](self-hosting.md) for the full variable reference.

### 3 — Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

### 4 — Install and run the frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### 5 — Install the SDK (editable)

```bash
cd backend/sdk/python
pip install -e ".[server,dev]"
```

### 6 — Seed demo data (optional)

```bash
cd backend
python scripts/seed_demo.py
```

---

## Running Tests

### Backend

```bash
cd backend
pytest tests/ -x -q
```

### SDK

```bash
cd backend/sdk/python
pytest tests/ -x -q
```

### Frontend type-check

```bash
cd frontend
npx tsc --noEmit
```

### Frontend build (must pass before any merge)

```bash
cd frontend
npm run build
```

All four must pass before submitting a PR.

---

## Test Standards

### Naming

Test names describe behavior, not implementation:

```
test_jira_adapter_normalizes_missing_description   ✓
test_normalize                                      ✗
```

### Required coverage per new route

Every new API route needs at minimum:

| Case | What to assert |
|------|---------------|
| Happy path | 200/201, correct response shape |
| Auth rejection | 401 when `X-Agent-Key` missing or invalid |
| Not found | 404 when resource doesn't exist |
| Edge cases | Empty lists, missing optional fields, boundary values |

### Mocking

- Use `respx` for HTTP mocking in SDK tests.
- Do not mock the database in backend integration tests. Tests run against SQLite in-memory — use that.
- If you must mock the DB for a specific test, mark it clearly with a comment explaining why.

### Async

Backend tests use `pytest-asyncio`. Mark async tests with `@pytest.mark.asyncio`.

---

## Code Standards

These are enforced at review. Non-compliance blocks merge.

### Python

- Full type annotations on all functions — parameters and return types.
- `Any` is only acceptable for JSONB fields (`dict[str, Any]`).
- Functions ≤ 40 lines. Extract helpers when exceeded.
- No dead code, no commented-out blocks, no `TODO`/`FIXME` left behind.
- No `print()` — use structured logging if needed.

### TypeScript

- No `any`. Types live close to usage.
- No God-type files.

### Comments

Write a comment only when the WHY is non-obvious — a hidden constraint, a subtle invariant, a workaround for a specific bug.

```python
# JSONB on Postgres, JSON on SQLite       ← good: documents a constraint
# returned only on creation, never again  ← good: documents a security invariant
# iterate over events                     ← bad: the code already says this
```

### SQL

All queries use SQLAlchemy ORM or parameterized `select()`. No string-interpolated SQL. Ever.

### HTTP bodies

All request bodies go through Pydantic models. No raw `dict` from `request.body()`.

---

## Key Invariants

Violating these is a critical bug:

- **`Ticket.body` is immutable.** Never mutate after import.
- **`agent_events` is append-only.** No UPDATE, no DELETE on that table.
- **Cost is computed at read time.** Never persist a derived cost value.
- **API keys stored hashed.** `Agent.api_key_hash` = SHA-256. Never log the raw key.
- **Workspace isolation.** Every DB query filters by `workspace_id`. Cross-tenant leakage is a critical security bug.

See [security.md](security.md) for the full threat model.

---

## PR Process

### Branch naming

```
feat/<short-description>
fix/<short-description>
docs/<short-description>
refactor/<short-description>
```

### Commits

- Imperative mood: `Add OAuth callback endpoint`, not `Added` or `Adding`.
- Subject line ≤ 72 characters.
- One logical change per commit. Don't bundle unrelated fixes.
- No `--no-verify`. If a hook fails, fix the underlying issue.

### Before opening a PR

- [ ] All tests pass (`pytest tests/ -x -q` in both `backend/` and `backend/sdk/python/`)
- [ ] Frontend build passes (`npm run build`)
- [ ] TypeScript clean (`npx tsc --noEmit`)
- [ ] No dead code, no TODOs, no commented-out blocks
- [ ] New routes have happy path + 401 + 404 tests
- [ ] New adapters have a test in `backend/tests/test_adapters.py`

### PR description

Include:
- What changed and why (not a rehash of the diff)
- How to test it manually
- Any security implications

### Review turnaround

Maintainers aim to review within 48 hours. If blocked on a question, comment on the PR — don't open a new issue.

---

## Adding New Features

### New ticket source

1. Create `backend/app/services/adapters/<source>.py` implementing `TicketAdapter`.
2. Register in `backend/app/services/adapters/__init__.py` `ADAPTERS` dict.
3. Add `source` literal to `ImportTicketRequest` in `tickets.py`.
4. Add tests in `backend/tests/test_adapters.py`.
5. Update `BulkImportRequest.source` if bulk import is supported.

### New event type

1. Add the literal to `EventRequest.event_type` in `events.py`.
2. Handle side effects in `post_event()`.
3. Update `AgentEvent` model docstring comment.
4. Add a typed method to `TrecoClient` in the SDK.

### New route module

1. Create `backend/app/api/routes/<name>.py`.
2. Mount in `backend/app/api/router.py`.
3. All routes need Pydantic request/response models.
4. Any route accessing agent-scoped data must call `_resolve_agent()` first — see `events.py` for the canonical pattern.

---

## Getting Help

Open an issue on GitHub with a clear reproduction case. For security issues, see [security.md](security.md) — do not open a public issue.
