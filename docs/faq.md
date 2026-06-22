# FAQ

---

## Does Treco work with Cursor, Codex, Windsurf, or any other AI agent?

Yes. The Claude Code hooks installed by `treco init` are specific to Claude Code, but Treco is not tied to any agent runtime.

Any agent can report to Treco using the Python SDK:

```python
from treco import TrecoClient

async with TrecoClient() as client:
    async with client.track(ticket_id):
        await client.log(ticket_id, "Starting task")
        await client.check(ticket_id, criterion_id="abc123", tokens_in=500, tokens_out=200)
```

For agents that don't support Python, Treco exposes a plain HTTP API. Any agent that can make HTTP requests can post events directly to `POST /api/events/`.

Claude Code gets zero-config tracking via hooks — other agents require a few lines of instrumentation.

---

## What data does Treco store?

Treco stores the minimum needed to track agent work:

| What | Details |
|------|---------|
| Tickets | Title, description, acceptance criteria, raw provider body (immutable after import) |
| Agent records | Machine hostname, SHA-256 hash of API key (raw key never stored) |
| Events | Event type, criterion ID, token counts (in/out), model name, timestamp, free-form payload |
| Workspace ID | A string namespace you set — no user PII required |

No source code is stored. No file contents. No conversation transcripts. The `payload` field on events holds whatever you pass (log messages, PR URLs, error strings) — keep that in mind if you log sensitive values.

All data is stored in your local SQLite file (`treco.db`) by default. With a PostgreSQL `DATABASE_URL`, it goes to your Postgres instance. Nothing leaves your machine unless you configure a remote database.

---

## Can I use PostgreSQL instead of SQLite?

Yes. Set two environment variables before starting the backend:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
DATABASE_MODE=postgres
```

Treco uses SQLAlchemy async with a `JSONB`/`JSON` type alias (`AnyJSON`) that maps to `JSONB` on Postgres and `JSON` on SQLite automatically. Schema creation (`CREATE TABLE`) runs on startup — no manual migration needed for a fresh database.

SQLite is fine for a single developer. Postgres is recommended if multiple agents write concurrently or if you want to retain data across machines.

---

## How accurate is cost tracking?

Cost is computed from token counts that agents report, not measured by Treco itself. Accuracy depends on what your agent reports.

**Claude Code hooks** capture token usage directly from tool call metadata — this is what the Claude Code extension exposes per tool call, so it reflects actual usage as closely as the API reports it.

**SDK users** pass `tokens_in` and `tokens_out` manually per event. If your agent runtime exposes token counts from the API response, pass them through. If not, you can estimate or omit them — events with zero tokens are valid and still appear in the event stream.

Cost is computed at read time by summing `tokens_in` and `tokens_out` across all events for a ticket. No cost value is ever persisted — if you update pricing constants, all historical tickets recalculate automatically.

Model pricing constants are not currently built into Treco. Cost display on the dashboard shows raw token counts. Per-dollar calculation is a planned feature.

---

## How does criteria extraction work?

When a ticket is created or imported, Treco sends the title and description to an LLM and asks it to return a JSON array of acceptance criteria.

Default model: `claude-haiku-4-5-20251001` (fast, cheap). Fallback model: `gpt-4o-mini` if `LLM_PROVIDER=openai`.

If no LLM API key is configured, or if the LLM call fails for any reason, Treco falls back to parsing markdown checkboxes from the description:

```
- [ ] Retry on 5xx up to 3 times
- [ ] Exponential backoff with jitter
- [x] Log each retry attempt   ← pre-checked
```

Extraction runs once at ticket creation time, never on reads. Criteria are stored alongside the ticket and can be checked off individually as the agent works.

---

## Do I need an LLM API key?

No. It's optional.

Without an API key, criteria extraction falls back to the markdown checkbox parser. If your tickets use `- [ ]` checkboxes in their description (GitHub Issues, Linear, Jira all support this), criteria are extracted without any LLM call.

To enable LLM extraction, set one of:

```bash
ANTHROPIC_API_KEY=sk-ant-...   # uses claude-haiku-4-5-20251001
OPENAI_API_KEY=sk-...          # set LLM_PROVIDER=openai too
```

---

## Can I self-host Treco for a team?

Yes. Run the backend on any machine with Docker and point your agents at it via `TRECO_URL`.

```bash
docker compose up   # starts backend + frontend
```

Set `DATABASE_URL` to a Postgres instance so multiple agents can write concurrently and data persists across restarts. See [Self-hosting](self-hosting.md) for the full setup guide.

Workspace isolation is enforced at the query level — every DB query filters by `workspace_id`. Multiple teams can share one backend using separate workspace IDs.

---

## What ticket sources are supported?

| Source | Import command |
|--------|---------------|
| GitHub Issues | `treco import https://github.com/org/repo/issues/42` |
| Linear | `treco import https://linear.app/team/issue/ENG-42` |
| Jira | `treco import <jira-url>` (requires `JIRA_TOKEN` in config) |
| Manual | `treco new "Ticket title"` |
| Custom | POST to `/api/tickets/` with `source: "custom"` |

Asana support is implemented in the adapter layer but not yet wired to the CLI import command.

Each source has a dedicated adapter (`backend/app/services/adapters/`) that normalizes provider-specific JSON into a common schema. Raw provider JSON is stored immutably in `ticket.body` — normalized fields are derived from it.

---

## Is my code or ticket content sent to Anthropic or OpenAI?

Only ticket **title and description** are sent during criteria extraction, and only if you have an LLM API key configured. No source code, no file contents, no agent event payloads are sent to any external service.

If you use `LLM_PROVIDER=anthropic`, the extraction call goes to Anthropic's API under your API key and is subject to Anthropic's data policies. If you want zero external calls, skip the API key and use markdown checkbox fallback instead.

---

## How do I reset a workspace or switch to a different one?

**Switch workspace:** edit `~/.treco/config.json` and change `workspace_id`, then run `treco init` against the new workspace. Each workspace is an isolated namespace — tickets and agents in workspace A are invisible to workspace B.

**Reset a workspace:** delete all tickets and agents from the dashboard, or drop and recreate the database. With SQLite: `rm treco.db` and restart the backend (schema is recreated on startup). With Postgres: `DROP DATABASE` and recreate.

**Re-init an agent:** if `treco init` fails because an agent with your hostname already exists, either delete the agent from the dashboard or use a different `workspace_id`.
