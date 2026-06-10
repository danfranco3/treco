# Treco — Implementation Plan: Real-Time Monitoring & Agent Launch

**Goal:** Users open the dashboard and see agent progress update live without any action.
They can register agents, assign tickets, and launch agent sessions from the UI.

---

## Audit: What's Broken or Missing Today

### Backend
| # | Issue | Severity |
|---|-------|----------|
| B1 | No SSE endpoint — frontend polls at 3–10s intervals, up to 10s lag | High |
| B2 | No workspace-level event stream — only per-ticket events exist | High |
| B3 | `last_seen_at` on Agent never updated when events arrive | Medium |
| B4 | No "assign ticket to agent" endpoint | High |
| B5 | Linear bulk import interpolates `team_key` into GraphQL query string — injection risk | Critical |
| B6 | `create_all` used for schema — dev-only, no migrations for prod | High |
| B7 | No pagination on `/tickets/` or `/agents/` — full table scan on every poll | Medium |
| B8 | Token costs not linked back to per-agent summary — requires N queries per dashboard | Medium |

### Frontend
| # | Issue | Severity |
|---|-------|----------|
| F1 | `useActiveEvents` in dashboard hardcodes 6 SWR hooks — breaks at 7+ active agents | High |
| F2 | No SSE/EventSource client — all updates are polling | High |
| F3 | No "Register agent" UI — CLI-only via `treco init` | High |
| F4 | No "Assign ticket to agent" action in UI | High |
| F5 | No "Launch agent" flow — zero first-time user guidance | High |
| F6 | `AgentCard` cost pill always shows 0 — cost data not wired in | Medium |
| F7 | SWR: no `revalidateOnFocus: false`, no `dedupingInterval` — excess requests | Low |
| F8 | No empty state / onboarding for new workspace | Medium |
| F9 | Ticket list has no pagination — all tickets loaded on every render | Medium |
| F10 | No agent detail page — can't see full history for one agent | Medium |

---

## Phase 1 — Real-Time Backend (SSE)

**What:** Replace polling with server-sent events. One persistent connection per workspace.
All state changes (agent status, criteria checked, new events) push to the client instantly.

### 1.1 Install `sse-starlette`

```
pip install sse-starlette
```

Add to `requirements.txt`.

### 1.2 Workspace event stream endpoint

**File:** `backend/app/api/routes/events.py`

Add `GET /events/stream?workspace_id=X`:

```python
from sse_starlette.sse import EventSourceResponse
import asyncio, json

@router.get("/stream")
async def event_stream(workspace_id: str, db: AsyncSession = Depends(get_db)):
    async def generator():
        # Bootstrap: last 50 events on connect so UI isn't empty
        result = await db.execute(
            select(AgentEvent)
            .where(AgentEvent.workspace_id == workspace_id)
            .order_by(AgentEvent.created_at.desc())
            .limit(50)
        )
        bootstrap = list(reversed(result.scalars().all()))
        for event in bootstrap:
            yield {"data": json.dumps(_event_to_dict(event))}

        last_created = bootstrap[-1].created_at if bootstrap else None

        while True:
            await asyncio.sleep(0.5)
            q = (
                select(AgentEvent)
                .where(AgentEvent.workspace_id == workspace_id)
                .order_by(AgentEvent.created_at)
            )
            if last_created:
                q = q.where(AgentEvent.created_at > last_created)
            result = await db.execute(q)
            for event in result.scalars().all():
                yield {"data": json.dumps(_event_to_dict(event))}
                last_created = event.created_at

    return EventSourceResponse(generator())
```

Design notes:
- **Bootstrap on connect**: fresh page load is not empty
- **500ms check inside generator**: ~20× cheaper than HTTP polling (1 persistent connection vs polling)
- **No WebSocket**: SSE is unidirectional server→client — correct for this use case
- **Disconnect cleanup**: `EventSourceResponse` handles client disconnect; the generator loop exits

### 1.3 Agent status stream endpoint

**File:** `backend/app/api/routes/agents.py`

Add `GET /agents/stream?workspace_id=X`:

```python
@router.get("/stream")
async def agent_stream(workspace_id: str, db: AsyncSession = Depends(get_db)):
    async def generator():
        last_snapshot: dict[str, str] = {}
        while True:
            result = await db.execute(
                select(Agent).where(Agent.workspace_id == workspace_id)
            )
            for agent in result.scalars().all():
                prev = last_snapshot.get(agent.id)
                if prev != f"{agent.status}:{agent.current_ticket_id}":
                    last_snapshot[agent.id] = f"{agent.status}:{agent.current_ticket_id}"
                    yield {"data": json.dumps({
                        "id": agent.id,
                        "name": agent.name,
                        "status": agent.status,
                        "current_ticket_id": agent.current_ticket_id,
                    })}
            await asyncio.sleep(0.5)

    return EventSourceResponse(generator())
```

### 1.4 Update `last_seen_at` on event POST

**File:** `backend/app/api/routes/events.py`, `post_event()`:

```python
from datetime import datetime
# Inside post_event(), after resolving agent:
agent.last_seen_at = datetime.utcnow()
```

### 1.5 Add workspace-level event list endpoint

**File:** `backend/app/api/routes/events.py`

```python
@router.get("/")
async def list_workspace_events(
    workspace_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.workspace_id == workspace_id)
        .order_by(AgentEvent.created_at.desc())
        .limit(min(limit, 500))
    )
    return result.scalars().all()
```

---

## Phase 2 — Real-Time Frontend (EventSource)

**What:** Replace SWR polling with `EventSource`. Use SWR only for initial loads and mutations.

### 2.1 New hooks: `useWorkspaceStream` + `useAgentStream`

**File:** `frontend/lib/hooks.ts`

```typescript
import { useEffect } from "react";
import { useSWRConfig } from "swr";
import type { AgentEvent, Agent } from "./types";

export function useWorkspaceStream(workspaceId: string) {
  const { mutate } = useSWRConfig();

  useEffect(() => {
    if (!workspaceId) return;
    const es = new EventSource(
      `/api/events/stream?workspace_id=${encodeURIComponent(workspaceId)}`
    );

    es.onmessage = (e) => {
      const event: AgentEvent = JSON.parse(e.data);

      // Update per-ticket event list instantly, no extra HTTP
      mutate(
        ["events", event.ticket_id],
        (prev: AgentEvent[] = []) =>
          prev.some((ev) => ev.id === event.id) ? prev : [...prev, event],
        { revalidate: false }
      );
      // Also update workspace-level event list
      mutate(
        ["workspace-events", workspaceId],
        (prev: AgentEvent[] = []) =>
          prev.some((ev) => ev.id === event.id) ? prev : [...prev, event],
        { revalidate: false }
      );
      // Revalidate ticket + cost for accuracy
      mutate(["ticket", event.ticket_id]);
      mutate(["cost", event.ticket_id]);
    };

    return () => es.close();
  }, [workspaceId, mutate]);
}

export function useAgentStream(workspaceId: string) {
  const { mutate } = useSWRConfig();

  useEffect(() => {
    if (!workspaceId) return;
    const es = new EventSource(
      `/api/agents/stream?workspace_id=${encodeURIComponent(workspaceId)}`
    );

    es.onmessage = (e) => {
      const updated: Agent = JSON.parse(e.data);
      mutate(
        ["agents", workspaceId],
        (prev: Agent[] = []) =>
          prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a)),
        { revalidate: false }
      );
    };

    return () => es.close();
  }, [workspaceId, mutate]);
}

export function useWorkspaceEvents(workspaceId: string) {
  return useSWR(
    workspaceId ? ["workspace-events", workspaceId] : null,
    () => fetchWorkspaceEvents(workspaceId),
    { refreshInterval: 30_000 }  // SSE is primary; this is fallback only
  );
}
```

### 2.2 `StreamProvider` — mount streams at root

**File:** `frontend/lib/StreamProvider.tsx` (new file)

```typescript
"use client";
import { useWorkspace } from "./workspace";
import { useWorkspaceStream, useAgentStream } from "./hooks";

export function StreamProvider({ children }: { children: React.ReactNode }) {
  const { workspaceId } = useWorkspace();
  useWorkspaceStream(workspaceId);
  useAgentStream(workspaceId);
  return <>{children}</>;
}
```

**File:** `frontend/app/layout.tsx` — add `<StreamProvider>` inside `<WorkspaceProvider>`.

### 2.3 Fix dashboard event feed

**File:** `frontend/app/dashboard/page.tsx`

Replace the fragile `useActiveEvents` pattern (hardcoded 6 hooks) with `useWorkspaceEvents`:

```typescript
const { data: events = [] } = useWorkspaceEvents(workspaceId);
```

No more 6-hook hack. Works for any number of active agents.

### 2.4 Lower SWR poll intervals (SSE is now primary)

```typescript
// hooks.ts — all hooks
{ refreshInterval: 30_000 }  // was 3_000–10_000; SSE handles live updates
```

---

## Phase 3 — Agent Registration & Ticket Assignment from UI

### 3.1 "Register Agent" modal

**File:** `frontend/app/agents/page.tsx`

Add "Register agent" button that opens a two-step modal:

**Step 1 — Name input:**
```
Name  ___________
[ Register ]
```

**Step 2 — Show key (once):**
```
API Key (save this — shown only once):
┌────────────────────────────────────┐
│ treco_aBcDeFgH...            [Copy] │
└────────────────────────────────────┘

Start this agent:
┌────────────────────────────────────┐
│ TRECO_API_KEY=treco_... treco start │
└────────────────────────────────────┘
[ Copy command ]     [ Done ]
```

Calls `POST /api/agents/` with `{ workspace_id, name }`.
On success, display the `api_key` from response — **never cache it, never re-show it**.

### 3.2 "Assign ticket to agent" backend

**File:** `backend/app/api/routes/agents.py`

```python
class AssignRequest(BaseModel):
    ticket_id: str

@router.post("/{agent_id}/assign")
async def assign_ticket(
    agent_id: str,
    req: AssignRequest,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status == "working":
        raise HTTPException(409, "Agent already working on a ticket")

    agent.status = "working"
    agent.current_ticket_id = req.ticket_id
    agent.last_seen_at = datetime.utcnow()
    db.add(agent)

    event = AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=req.ticket_id,
        workspace_id=agent.workspace_id,
        event_type="ticket_started",
        payload={"source": "ui_assign"},
    )
    db.add(event)
    await db.commit()
    return {"ok": True}
```

Note: append-only invariant preserved — this creates a new event, not an update.

### 3.3 "Assign" UI on ticket detail

**File:** `frontend/app/tickets/[id]/page.tsx`

When `activeAgent` is null and there are idle agents:

```
No agent working this ticket.

Assign:  [Select agent ▾]  [ Assign ]
```

Or show "Copy launch command":

```
[ Copy: treco start <ticket-id> ]
```

Both paths get the ticket moving.

### 3.4 Launch instructions callout

**File:** `frontend/app/agents/page.tsx`

Shown when no agents are working:

```
┌──────────────────────────────────────────────────────────────┐
│  No agents running. To start one:                            │
│                                                              │
│    pip install treco                                         │
│    treco init     # connects to this server                  │
│    treco start    # picks a ticket and begins tracking       │
│                                                              │
│  Claude Code users: treco hook install auto-tracks tokens.  │
└──────────────────────────────────────────────────────────────┘
```

Dismissible, stored in `localStorage`.

---

## Phase 4 — Security Fix (Critical, Do First)

**File:** `backend/app/api/routes/tickets.py`, line ~226

**Current (vulnerable):**
```python
team_filter = f'(filter: {{ team: {{ key: {{ eq: "{req.team_key}" }} }} }})'
query = f"query {{ issues{team_filter} {{ nodes {{ ... }} }} }}"
```

A `team_key` value of `"}}){malicious}query{{"` can inject arbitrary GraphQL.

**Fix — use GraphQL variables:**
```python
if req.team_key:
    query = """
        query($teamKey: String!) {
            issues(filter: { team: { key: { eq: $teamKey } } }) {
                nodes { identifier title description state { name } }
            }
        }
    """
    variables: dict = {"teamKey": req.team_key}
else:
    query = """
        query {
            issues(first: 50) {
                nodes { identifier title description state { name } }
            }
        }
    """
    variables = {}

r = await client.post(
    "https://api.linear.app/graphql",
    json={"query": query, "variables": variables},
    headers={"Authorization": req.token, "Content-Type": "application/json"},
)
```

Also validate `req.team_key` matches `^[A-Z0-9_-]{1,20}$` at Pydantic level:

```python
from pydantic import field_validator
import re

class BulkImportRequest(BaseModel):
    team_key: str | None = None

    @field_validator("team_key")
    @classmethod
    def validate_team_key(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[A-Z0-9_-]{1,20}", v):
            raise ValueError("team_key must be uppercase alphanumeric, 1–20 chars")
        return v
```

---

## Phase 5 — Pagination

**Backend:** `backend/app/api/routes/tickets.py`

```python
@router.get("/")
async def list_tickets(
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .where(Ticket.workspace_id == workspace_id)
        .order_by(Ticket.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    return result.scalars().all()
```

**Frontend:** `frontend/app/tickets/page.tsx` — "Load more" button with `offset` state.

---

## Phase 6 — Agent Detail Page

**What:** `/agents/[id]` — full history for one agent.

**Backend endpoint:** `GET /events/agent/{agent_id}?limit=200`

```python
@router.get("/agent/{agent_id}")
async def get_agent_events(agent_id: str, limit: int = 200, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.agent_id == agent_id)
        .order_by(AgentEvent.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
```

**Frontend:** `frontend/app/agents/[id]/page.tsx`
- Agent header: name, status, last seen
- Tickets worked: derived from events (distinct `ticket_id` values)
- Cumulative token cost
- Full event timeline (reuse `TicketEventLog` component)

Make `AgentCard` link to `/agents/[agent.id]`.

---

## Phase 7 — Alembic Migrations

**What:** `create_all` is dev-only. Prod needs schema migrations.

```bash
cd backend
pip install alembic
alembic init migrations
```

Configure `migrations/env.py`:
```python
from app.core.config import settings
from app.core.database import Base
import app.models  # registers all models

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

```bash
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

Update `Dockerfile`:
```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
```

Update `backend/app/core/database.py`: remove `create_all` from `init_db()` (replaced by migrations).

---

## Phase 8 — First-Time Onboarding

**File:** `frontend/app/dashboard/page.tsx`

If `agents.length === 0 && tickets.length === 0` and not dismissed:

```tsx
<OnboardingCard onDismiss={() => setDismissed(true)} workspaceId={workspaceId} />
```

Content:
1. Install: `pip install treco`
2. Configure: `treco init` (with server URL pre-filled)
3. Import: `treco import <github-url>`
4. Track: `treco start`

Or: `[ Register agent from here ]` button as shortcut to Phase 3 modal.

---

## Execution Order

| Priority | Work | Effort | Impact |
|----------|------|--------|--------|
| **1** | Phase 4 — GraphQL injection fix | 30 min | **Critical security** |
| **2** | Phase 1 — SSE backend | 2h | Core: live updates |
| **3** | Phase 2 — SSE frontend + StreamProvider | 2h | Core: live updates |
| **4** | Phase 3 — Agent register + assign | 3h | Core: launch flow |
| **5** | Phase 8 — Onboarding | 1h | First impression |
| **6** | Phase 5 — Pagination | 1h | Performance |
| **7** | Phase 6 — Agent detail page | 2h | Completeness |
| **8** | Phase 7 — Alembic | 1h | Prod readiness |

Total: ~13h focused implementation.

---

## Invariants to Preserve

- `agent_events` is append-only — assign endpoint creates a new `ticket_started` event, no UPDATEs
- `Ticket.body` stays immutable — no route touches it post-import
- `api_key_hash` only in DB — raw key returned once on create, never re-exposed
- All SSE streams filter by `workspace_id` — no cross-tenant leakage
- SSE generator must open a **fresh DB session** per generator invocation (do not share session across `yield`s)
- Cost is always computed at read time from `SUM(tokens_in/out)` — never stored as a derived field

---

## Testing Checklist

**SSE / real-time:**
- [ ] Open dashboard → event feed populates without manual refresh
- [ ] `curl POST /api/events/` → appears in feed < 1s
- [ ] Close/reopen tab → bootstrap events load immediately on reconnect
- [ ] Kill backend → frontend shows stale indicator; reconnects when backend returns

**Agent launch:**
- [ ] Register agent → API key shown once → refreshing modal does NOT show key again
- [ ] Assign ticket to idle agent → AgentCard transitions to "working" in real time (via SSE)
- [ ] Assign to already-working agent → 409 error shown in UI
- [ ] `treco start` from terminal → dashboard reflects working state < 1s

**Security:**
- [ ] `team_key='"}}'` → returns 422 validation error, not a GraphQL result
- [ ] Valid team key `ENG` → imports correctly

**Pagination:**
- [ ] 200-ticket workspace → first load shows 50 → "Load more" gets next 50

**Onboarding:**
- [ ] Fresh workspace → onboarding card shown
- [ ] Dismiss → localStorage flag set → card hidden on reload
- [ ] Any agent created → card auto-hides
