# Contributing to Treco

Thanks for your interest. This covers setup, standards, and the PR process.

---

## Setup

**Requirements:** Python 3.11+, Node.js 18+

```bash
git clone https://github.com/danfranco3/treco
cd treco

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env         # edit JWT_SECRET

# Frontend
cd ../frontend
npm install

# SDK (editable)
cd ../backend/sdk/python
pip install -e ".[server,dev]"
```

Start everything:

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8001

# Terminal 2
cd frontend && npm run dev
```

Seed demo data: `cd backend && python scripts/seed_demo.py`

---

## Running tests

All four must pass before submitting a PR.

```bash
# Backend (220 tests)
cd backend && pytest tests/ -x -q

# SDK
cd backend/sdk/python && pytest tests/ -x -q

# TypeScript type check
cd frontend && npx tsc --noEmit

# Frontend build (must pass)
cd frontend && npm run build
```

---

## What belongs in a PR

### New API route
- Pydantic request + response models
- Happy path test, 404 test, auth rejection test (401 on event routes)
- Route mounted in `api/router.py`

### New ticket source (adapter)
1. `backend/app/services/adapters/<source>.py` implementing `TicketAdapter`
2. Registered in `adapters/__init__.py` `ADAPTERS` dict
3. `source` literal added to `ImportTicketRequest`
4. Tests in `backend/tests/test_adapters.py`

### New event type
1. Literal added to `EventRequest.event_type`
2. Side effects handled in `post_event()`
3. Typed method added to `TrecoClient` in the SDK

---

## Code rules

**Python**
- Full type annotations everywhere. `Any` only for JSONB fields.
- Functions ≤ 40 lines. Extract helpers beyond that.
- No `print()`. No dead code. No `TODO`/`FIXME` in PRs.
- All DB queries use SQLAlchemy ORM or parameterized `select()`. No string SQL.

**TypeScript**
- No `any`. Types close to usage.

**Comments**
- Only when the WHY is non-obvious. Never explain what the code does.

**Tests**
- Names describe behavior: `test_jira_adapter_normalizes_missing_description` not `test_normalize`.
- Do not mock the DB in backend tests. Tests run against SQLite in-memory — use `TestSessionLocal`.
- Use `respx` for HTTP mocking in SDK tests.

---

## Key invariants — never violate

- `Ticket.body` is immutable after import. Never mutate.
- `agent_events` is append-only. No UPDATE, no DELETE, ever.
- Cost is computed at read time from token sums. Never persist a derived value.
- `Agent.api_key_hash` is SHA-256. Never log or return the raw key.
- All DB queries filter by `workspace_id`. Cross-tenant data access is a critical bug.

---

## PR checklist

- [ ] `pytest tests/ -x -q` passes in `backend/` and `backend/sdk/python/`
- [ ] `npm run build` passes
- [ ] `npx tsc --noEmit` passes
- [ ] New routes have happy path + 404 + auth rejection tests
- [ ] No TODOs, no commented-out code, no dead imports
- [ ] PR description explains what changed and why (not a diff summary)

---

## Security issues

Do not open a public issue for security bugs. See [docs/security.md](docs/security.md) for the responsible disclosure process.
