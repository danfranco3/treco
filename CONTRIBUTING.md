# Contributing to Treco

Thanks for your interest. This covers setup, standards, and the PR process.

---

## Before you start

- Sign the [Contributor License Agreement](https://cla-assistant.io/danfranco3/treco). The cla-assistant bot will comment on your first PR with a link — it takes 30 seconds. PRs cannot be merged without it.
- For significant changes, open an issue first to align on approach before writing code.

**Why a CLA:** Treco is AGPL v3. The CLA lets the maintainer offer commercial licenses to enterprises without being bound by every contributor's copyright. Your rights as an open source user are unaffected.

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
# Backend integration tests
cd backend && pytest tests/ -x -q

# SDK unit tests
cd backend/sdk/python && pytest tests/ -x -q

# TypeScript type check
cd frontend && npx tsc --noEmit

# Frontend build (must pass)
cd frontend && npm run build
```

---

## What belongs in a PR

### New API route
- Pydantic request + response models on the handler
- Happy path test, 404 test, auth rejection test (401 on agent-authenticated routes)
- Route mounted in `api/router.py`

### New event type
1. Literal added to `EventRequest.event_type` in `events.py`
2. Side effects handled in `post_event()`
3. Typed method added to `TrecoClient` in the SDK

### Frontend components
- No `any` in TypeScript
- Test the golden path in a browser before submitting
- Dark and light theme both work

---

## Code rules

**Python**
- Full type annotations everywhere. `Any` only for JSONB fields.
- Functions ≤ 40 lines. Extract named helpers beyond that.
- No `print()`. No dead code. No `TODO`/`FIXME` in PRs.
- All DB queries use SQLAlchemy ORM or parameterized `select()`. No string-interpolated SQL.
- All route handlers have explicit return type annotations and Pydantic response models.

**TypeScript**
- No `any`. Types live close to usage; no God-type files.
- SWR for data fetching. No raw `fetch` in components.

**Comments**
- Default: none. Write one only when the WHY is non-obvious — a hidden constraint, a subtle invariant, a known bug workaround.
- Never explain what the code does. Never reference issue numbers or callers.

**Tests**
- Names describe behavior: `test_event_marks_agent_working` not `test_event`.
- Do not mock the DB in backend tests. Tests run against SQLite in-memory via `TestSessionLocal`.
- Use `respx` for HTTP mocking in SDK tests.
- Every new route needs at minimum: happy path, 404, and auth rejection.

---

## Key invariants — never violate

- `Ticket.body` is immutable after import. Never mutate.
- `agent_events` is append-only. No UPDATE, no DELETE on that table, ever.
- Cost is computed at read time from token sums. Never persist a derived cost value.
- `Agent.api_key_hash` is SHA-256. Never log or return the raw key in any response.
- All DB queries filter by `workspace_id`. Cross-tenant data access is a critical bug.

---

## PR checklist

- [ ] `pytest tests/ -x -q` passes in `backend/` and `backend/sdk/python/`
- [ ] `npm run build` passes
- [ ] `npx tsc --noEmit` passes
- [ ] New routes have happy path + 404 + auth rejection tests
- [ ] No TODOs, no commented-out code, no dead imports (ruff will catch these)
- [ ] PR description explains what changed and why — not a diff summary

---

## Security issues

Do not open a public issue for security bugs. Email `danielscheurerfranco@gmail.com` with details. See [docs/security.md](docs/security.md) for the full responsible disclosure process.
