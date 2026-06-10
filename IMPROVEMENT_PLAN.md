# Treco Improvement Plan

Two parallel tracks: **stability** (make the happy path work end-to-end) and **UI** (make the dashboard trustworthy and excellent).

---

## Track 1 — Stability & Launch Readiness

### 1. E2E smoke test (priority 1)

Run the happy path on the actual machine. Nothing else matters if this is broken.

```bash
TRECO_BACKEND_DIR=./backend treco server start
treco init
treco import https://github.com/org/repo/issues/1
treco start
# simulate a hook payload manually:
echo '{"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{},"tool_response":{},"usage":{"input_tokens":1500,"output_tokens":320,"cache_creation_input_tokens":0,"cache_read_input_tokens":800}}' | treco hook post-tool-use
# open http://localhost:3000 and verify agent shows working, tokens increment
```

Pass criteria:
- Agent status changes idle → working
- Token counts visible and non-zero
- Criteria check marks off when `treco check <id>` runs
- Cost estimate non-zero

### 2. Fix backend tests

`JWT_SECRET` is required in `config.py` but unused in any route. Make it optional:

```python
# backend/app/core/config.py
jwt_secret: str = Field(default="dev-secret", alias="JWT_SECRET")
```

Or set it in the test env. Without this, `pytest backend/tests/` fails on collection.

### 3. Commit everything

All work is unstaged. Git status shows 11 modified/new files plus `PLAN.md`. Stage and commit before doing anything else that creates more drift.

### 4. Update README

README still shows `docker compose up`, port 8000, and manual hook setup. Replace with the actual flow:

```bash
pip install -e ./backend/sdk/python
treco init        # creates agent, starts server, wires Claude Code hooks
treco import <url>
treco start
# open http://localhost:3000
```

### 5. PyPI publish

`pyproject.toml` is ready. Steps:

```bash
cd backend/sdk/python
pip install build twine
python -m build
twine upload dist/*
```

Requires PyPI credentials. Do after E2E passes.

---

## Track 2 — UI Redesign

**Design north star:** PostHog dark — data-forward, excellent hierarchy, technical credibility without hacker aesthetic.
**Personality:** Clear. Calm. Confident.
**Anti-patterns to eliminate:** hero-metric stat cards, neon glow effects, weak type hierarchy, spinner-in-content loading.

The existing palette (dark navy bg `#0a0e1a`, cyan `#06b6d4`, Inter + JetBrains Mono) is correct — preserve it. Fix everything else.

---

### UI-1 — Design system consolidation

**File:** `frontend/app/globals.css`, `frontend/tailwind.config.ts`

Convert all color tokens to OKLCH. Add a complete semantic token set. Fix the `text-muted` contrast failure (`#6b7280` on `#111827` = ~4.2:1, fails AA at small sizes).

```css
:root {
  /* Backgrounds */
  --bg:        oklch(0.12 0.02 255);   /* #0a0e1a equivalent */
  --surface:   oklch(0.17 0.02 255);   /* #111827 */
  --surface-2: oklch(0.20 0.025 255);  /* #1a2235 */
  --surface-3: oklch(0.23 0.025 255);  /* hover surface */

  /* Borders */
  --border:    oklch(0.28 0.02 255);
  --border-focus: oklch(0.55 0.15 220); /* cyan at focus ring strength */

  /* Text — all must hit 4.5:1 on --surface */
  --text:       oklch(0.97 0.005 255);  /* primary body */
  --text-2:     oklch(0.72 0.01 255);   /* secondary — replaces #6b7280 which fails */
  --text-3:     oklch(0.52 0.01 255);   /* disabled/placeholder */

  /* Semantic accent */
  --cyan:   oklch(0.68 0.14 220);  /* #06b6d4 */
  --green:  oklch(0.70 0.14 160);
  --red:    oklch(0.60 0.20  25);
  --amber:  oklch(0.76 0.16  75);
  --purple: oklch(0.63 0.18 295);

  /* Z-index scale */
  --z-dropdown: 100;
  --z-sticky:   200;
  --z-modal-bg: 300;
  --z-modal:    310;
  --z-toast:    400;
  --z-tooltip:  500;
}
```

Add button, badge, and form-control vocabulary as `@layer components` in globals.css. Every interactive element uses these classes — never ad-hoc Tailwind chains for buttons.

Add `motion` package: `npm install motion` (Framer Motion v11). Replace manual CSS `@keyframes` with declarative variants.

---

### UI-2 — Stat bar replacement

**File:** `frontend/components/dashboard/StatBar.tsx`

The current 3-card hero-metric grid (big number + icon + colored label) is the banned "hero-metric template." Replace with a compact inline status strip — horizontal bar that reads left to right, not a grid of identical decorated boxes.

```
[ ◎  2 active  ·  ◈  14 open  ·  ✓  7 done today  ·  $ 0.84 today ]
```

- Single `<div>` with `flex gap-6 items-center px-4 py-2 bg-surface rounded-lg border border-border`
- Each stat: `<span class="text-sm font-mono text-cyan">N</span> <span class="text-xs text-text-2">label</span>`
- No cards. No icons floating in color. No 3xl font sizes.
- Separator dots between stats: `·` in `text-border`
- Token cost appended at the right, right-aligned with `ml-auto`

---

### UI-3 — Agent cards

**File:** `frontend/components/agents/AgentColumn.tsx` and `AgentCard.tsx`

Current cards: generic card with status badge. Replace with a design that reads like an instrument panel row.

Each agent card:
- Left edge: 3px solid indicator bar — `--cyan` when working, `--green` when done, `--border` when idle, `--red` when error. (This is a 3px solid on the card's left border — not the banned wide decorative side stripe. The distinction: it's a semantic state indicator at ≤3px, not a decorative accent.)
- Agent name in `font-mono text-sm text-text`
- Current ticket title truncated to 1 line: `text-xs text-text-2`
- Right: live token counter when working — ticks up in real time from `useTicketEvents`
- `agent-working` pulse animation only on the indicator bar when status = working, not on the whole card
- Skeleton state when loading (not Spinner)

Working column: cards have `bg-surface border-cyan/20` with the border-pulse animation on the border only.

---

### UI-4 — Ticket list density

**File:** `frontend/components/tickets/TicketRow.tsx`

Current rows: full cards with too much vertical padding. Replace with a proper data table row:

- `grid grid-cols-[1fr_120px_90px_100px_36px]` layout
- Columns: title / source badge / status badge / assignee (agent name or —) / progress ring
- `py-2.5 px-4` row padding
- Hover: `bg-surface-3` background, not a full border recolor
- Source badge: `font-mono text-xs` — "gh" / "linear" / "jira" / "custom"
- Status badge: filled pill — `bg-green/15 text-green` for done, `bg-cyan/15 text-cyan` for in_progress, `bg-surface-2 text-text-2` for open
- Progress ring: `<ProgressRing>` component, 24px, shows % criteria done

Replace inline `<Spinner />` in page header with per-row skeleton rows during loading (3 skeleton rows: shimmer animation on a rounded rect).

---

### UI-5 — Ticket detail page

**File:** `frontend/app/tickets/[id]/page.tsx` and components in `frontend/components/ticket-detail/`

Three-column layout at ≥1280px, two-column at ≥768px, single at mobile:

```
[ Ticket header + description ]  [ Criteria checklist ]  [ Cost panel ]
         2fr                              1fr                  1fr
```

**Criteria checklist:**
- Each criterion: checkbox (real `<input type="checkbox" disabled>` styled with CSS), criterion text, agent name + timestamp when done
- Done criteria: `line-through text-text-3`, checkmark in `--green`
- Pending: normal weight, `--text-2`
- Animated check when a criterion fires: `motion` scale-in on the checkmark

**Cost panel:**
- Total cost in `font-mono text-2xl text-text`
- Breakdown: input tokens / output tokens / cache write — 3 rows of `<dt>/<dd>` in a definition list
- Bar chart from Recharts — token spend per event, narrow bars, `--cyan` fill — at bottom of panel
- No card-within-card nesting

**Event feed:**
- `font-mono text-xs` — matches terminal aesthetic
- Timestamp: `text-text-3 tabular-nums w-[5ch]` left column
- Event type: colored badge `mr-2`
- Message: `text-text-2`
- `terminal-line-enter` animation on new items — keep this, it's correct

---

### UI-6 — Empty states

**File:** `frontend/components/ui/EmptyState.tsx`

Current empty states say "Nothing here." Replace with actionable empty states that teach the interface.

**No agents connected:**
```
◎  No agents connected yet

Run  treco init  in your project to connect this workspace.
```

**No tickets:**
```
◈  No tickets yet

Import from GitHub, Linear, or Jira — or create one manually.

[ Import tickets ]  [ New ticket ]
```

**Agent idle, no ticket:**
```
◎  Agent connected, waiting for a ticket

Run  treco start  to assign a ticket to this agent.
```

Format: centered vertically in the container, icon at `text-text-3`, heading at `text-sm font-medium text-text-2`, subtext at `text-xs text-text-3`, code snippets in `font-mono bg-surface-2 px-1.5 py-0.5 rounded text-cyan`, action buttons as secondary style.

---

### UI-7 — Skeleton loading states

**File:** new `frontend/components/ui/Skeleton.tsx`

Remove all `<Spinner>` from inside content areas. Replace with skeletons.

```tsx
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded bg-surface-2", className)}
      aria-hidden="true"
    />
  );
}
```

Add `@keyframes shimmer` in globals.css:
```css
@keyframes shimmer {
  from { background-position: -200% 0; }
  to   { background-position:  200% 0; }
}
.skeleton-shimmer {
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-3) 50%, var(--surface-2) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
```

Usage: ticket list → 5 skeleton rows. Stat strip → 3 skeleton spans. Agent columns → 2 skeleton cards per column.

---

### UI-8 — Command palette

**File:** new `frontend/components/ui/CommandPalette.tsx`

Keyboard shortcut: `Cmd+K` / `Ctrl+K`. Developer audience expects this.

Commands:
- `Go to dashboard`
- `Go to tickets`
- `Go to agents`
- `New ticket`
- `Import tickets`
- All ticket titles — fuzzy search, navigate to ticket detail on enter

Implementation:
- Native `<dialog>` element (not a div with `position: fixed`)
- `backdrop-blur-sm bg-bg/80` backdrop
- Input: `font-mono text-sm` placeholder `"Search tickets, navigate..."`
- Results list: `max-h-80 overflow-y-auto`
- Highlight matching chars with `<mark>` styled `bg-cyan/20 text-cyan rounded-sm`
- `motion` animate-in: `y: -8 → 0, opacity: 0 → 1, duration: 0.15s`
- Open on `Cmd+K`, close on `Escape` or outside click
- No external library needed — ~120 lines

---

### UI-9 — Motion system

**File:** `frontend/app/globals.css`, component files

Audit and systematize all animation. Rules:
- All transitions: 150ms for micro (hover, active), 200ms for reveal, 250ms for panel open
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)` (ease-in-out) for state changes; `cubic-bezier(0, 0, 0.2, 1)` (ease-out) for reveals
- Every animation: wrap in `@media (prefers-reduced-motion: reduce) { animation: none; transition: none; }`

Keep:
- `terminal-line-enter` on event feed items (state reveal — correct)
- `border-pulse` on working agent cards (state indicator — correct, just limit it to the border only)
- `ping-slow` on the live status dot (state indicator — correct)

Remove:
- Any glow box-shadow on the border-pulse (current: `box-shadow: 0 0 12px 2px rgba(6, 182, 212, 0.15)` — this is neon glow, anti-pattern)
- Page-load fade animations (product loads into a task)

Add via `motion` library:
- Command palette entrance: `initial={{ y: -8, opacity: 0 }} animate={{ y: 0, opacity: 1 }}`
- Criterion check: `initial={{ scale: 0 }} animate={{ scale: 1 }}` on checkmark icon
- Stat strip count change: number morphing via `motion` `animate={{ opacity: [0.5, 1] }}`

---

### UI-10 — Responsive layout

**File:** `frontend/app/layout.tsx`, `frontend/components/layout/Sidebar.tsx`

Current layout breaks below ~1100px (fixed 3-col grids).

Changes:
- Sidebar: collapse to icon-only at `<1024px`, hide entirely at `<768px` with hamburger toggle
- Dashboard grid: `grid-cols-1` at mobile, `grid-cols-2` at `≥768px`, `grid-cols-3` at `≥1280px`
- Ticket detail: stack columns at `<768px`
- Stat strip: wrap to 2 rows at `<640px`
- Agent kanban: `grid-cols-1` at mobile, `grid-cols-3` at `≥768px`

---

### UI implementation order

| # | Task | Effort | Impact |
|---|------|--------|--------|
| UI-1 | Design tokens (OKLCH, fix contrast) | S | Foundation for all below |
| UI-2 | Stat bar replacement | S | Removes biggest anti-pattern |
| UI-6 | Empty states | S | Critical for first-run UX |
| UI-7 | Skeleton loading | S | Removes jarring spinners |
| UI-4 | Ticket list density | M | Most-used screen |
| UI-3 | Agent cards | M | Core observability surface |
| UI-5 | Ticket detail | M | Where devs spend time |
| UI-9 | Motion system | S | Polish + correctness |
| UI-8 | Command palette | M | Developer delight |
| UI-10 | Responsive layout | M | Required before any public share |

---

## Definition of done

**Stability track:** a developer on a clean machine with Python 3.11+ runs `pip install -e ./backend/sdk/python && treco init && treco start && claude "implement the issue"` and sees live progress on the dashboard.

**UI track:** open the dashboard with seed data loaded. No hero-metric grids, no glow effects, no spinner-in-content, no contrast failures. Agent cards pulse subtly when active. Ticket list is dense and scannable. Criteria tick off with a quiet animation. `Cmd+K` opens a command palette. The interface feels like PostHog dark: data-forward, calm, trustworthy.
