# Python SDK — TrecoClient API Reference

Full reference for the `treco` Python package. Use this to instrument any async Python agent to report progress, token usage, and acceptance-criterion status to Treco in real time.

**Package:** `treco` · **PyPI:** `pip install treco` · **Requires:** Python 3.10+

---

## Installation

```bash
pip install treco
```

To also run the Treco backend locally from the same environment:

```bash
pip install "treco[server]"
```

---

## Configuration

`TrecoClient` reads credentials from constructor arguments or environment variables. Environment variables take effect when constructor arguments are not supplied.

| Source | Variable | Description |
|--------|----------|-------------|
| Constructor | `api_key` | Agent API key (takes priority) |
| Env var | `TRECO_API_KEY` | Agent API key fallback |
| Constructor | `base_url` | Backend URL (takes priority) |
| Env var | `TRECO_URL` | Backend URL fallback (default: `http://localhost:8001`) |
| Config file | `~/.treco/config.json` | Written by `treco init`; read automatically by the CLI, not by the SDK |

The config file is chmod 600. Never commit it or log its contents. The SDK does **not** read `~/.treco/config.json` — set `TRECO_API_KEY` or pass `api_key` directly.

---

## TrecoClient

```python
from treco import TrecoClient

class TrecoClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None: ...
```

Creates an async HTTP client bound to one agent identity. Internally wraps a single `httpx.AsyncClient` that is reused for the client's lifetime. Do not create a new `TrecoClient` per request or per event — create one per agent session.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str \| None` | `$TRECO_API_KEY` | Agent API key. Raises `KeyError` if absent and env var is not set. |
| `base_url` | `str \| None` | `$TRECO_URL` or `http://localhost:8001` | Treco backend URL. Trailing slash is stripped. |

**Examples**

```python
# From environment variables
client = TrecoClient()

# Explicit values
client = TrecoClient(api_key="sk-abc123", base_url="https://treco.example.com")
```

---

## Methods

All methods are `async`. All methods raise `httpx.HTTPStatusError` on non-2xx responses from the backend, and `httpx.RequestError` on network failures.

---

### `start`

```python
async def start(self, ticket_id: str) -> None
```

Emits `ticket_started`. Sets the agent's status to `working` and binds `current_ticket_id` on the backend. Call once when the agent begins work on a ticket.

```python
await client.start("b2e3f1a0-4c87-4d1e-b581-2e0c3f1a9d44")
```

---

### `heartbeat`

```python
async def heartbeat(self, ticket_id: str) -> None
```

Emits `heartbeat`. Updates `agent.last_seen_at` without changing status. An agent that goes 5 minutes without a heartbeat is marked offline by the backend.

The `track` context manager spawns a background task that calls this automatically every 60 seconds — you rarely need to call it manually.

```python
await client.heartbeat(ticket_id)
```

---

### `check`

```python
async def check(
    self,
    ticket_id: str,
    criterion_id: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    model: str | None = None,
) -> None
```

Emits `criterion_checked`. Sets `done = True` on the matching acceptance criterion in the database and records token usage for cost tracking.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ticket_id` | `str` | — | Ticket UUID |
| `criterion_id` | `str` | — | Criterion UUID from `ticket.acceptance_criteria[n].id` |
| `tokens_in` | `int` | `0` | Input tokens consumed completing this criterion |
| `tokens_out` | `int` | `0` | Output tokens consumed completing this criterion |
| `model` | `str \| None` | `None` | Model identifier, e.g. `"claude-sonnet-4-6"` |

```python
await client.check(
    ticket_id,
    criterion_id="3f1ab0a1-318c-423f-88a7-a7c88703f93a",
    tokens_in=1200,
    tokens_out=340,
    model="claude-sonnet-4-6",
)
```

---

### `fail_criterion`

```python
async def fail_criterion(
    self,
    ticket_id: str,
    criterion_id: str,
    reason: str = "",
) -> None
```

Emits `criterion_failed`. Records that the agent attempted but could not satisfy the criterion. Does **not** set `done = True` — the criterion remains open.

```python
await client.fail_criterion(
    ticket_id,
    criterion_id="3f1ab0a1-318c-423f-88a7-a7c88703f93a",
    reason="Integration test requires a live Postgres instance",
)
```

---

### `log`

```python
async def log(
    self,
    ticket_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None
```

Emits `log`. Appends a progress message visible in the dashboard event stream. `payload` is merged into the event body alongside `message` — use it for structured context the dashboard or downstream tools can consume.

Triggers the backend deviation detector.

```python
await client.log(ticket_id, "Running test suite")

# With structured context
await client.log(
    ticket_id,
    "File edited",
    payload={"file": "app/main.py", "lines_changed": 12},
)
```

---

### `done`

```python
async def done(
    self,
    ticket_id: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None
```

Emits `done`. Sets agent status to `idle`, clears `current_ticket_id`, and marks the ticket `done` in the database.

Pass cumulative session token totals here if you did not report them per-criterion via `check`. If you already reported tokens on every `check` call, pass `0` here to avoid double-counting.

The `track` context manager calls this automatically on clean exit.

```python
await client.done(ticket_id, tokens_in=8400, tokens_out=2100)
```

---

### `error`

```python
async def error(self, ticket_id: str, message: str) -> None
```

Emits `error`. Sets agent status to `error` and clears `current_ticket_id`. Does **not** mark the ticket done — it remains open for retry.

The `track` context manager calls this automatically on an unhandled exception, then re-raises the exception.

```python
await client.error(ticket_id, "Unrecoverable: upstream API returned 503")
```

---

### `track`

```python
@asynccontextmanager
async def track(self, ticket_id: str) -> AsyncIterator[TrecoClient]
```

Async context manager that manages the full session lifecycle:

1. Calls `start` on entry
2. Spawns a background task that calls `heartbeat` every 60 seconds
3. Calls `done` on clean exit
4. Calls `error` and re-raises on any unhandled exception
5. Cancels the heartbeat task in all cases (clean or exceptional)

Yields `self`, so you can use the same `treco` variable for all subsequent calls.

```python
async with client.track(ticket_id) as treco:
    await treco.log(ticket_id, "Starting")
    result = await do_work()
    await treco.check(
        ticket_id,
        criterion_id="3f1ab0a1-...",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        model="claude-sonnet-4-6",
    )
# done() called automatically here
```

---

### `close`

```python
async def close(self) -> None
```

Closes the underlying `httpx.AsyncClient`. Call this when managing the client lifetime manually (i.e. not via `track`).

```python
client = TrecoClient()
try:
    await client.start(ticket_id)
    # ... agent work ...
    await client.done(ticket_id)
finally:
    await client.close()
```

---

## Async Usage Patterns

### Pattern 1 — `track` (recommended)

`track` handles `start`, `done`, `error`, heartbeat, and cleanup automatically. Use this for any agent that has a defined start and end.

```python
import asyncio
from treco import TrecoClient

async def run_agent(ticket_id: str) -> None:
    client = TrecoClient()
    try:
        async with client.track(ticket_id) as treco:
            await treco.log(ticket_id, "Fetching ticket context")
            result = await do_analysis()
            await treco.check(
                ticket_id,
                criterion_id=result.criterion_id,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                model="claude-sonnet-4-6",
            )
    finally:
        await client.close()

asyncio.run(run_agent("b2e3f1a0-4c87-4d1e-b581-2e0c3f1a9d44"))
```

### Pattern 2 — Manual lifecycle

Use when you need finer control over when `start` and `done` are called, or when reporting is fire-and-forget and you don't want the exception re-raise behavior of `track`.

```python
async def run_agent(ticket_id: str) -> None:
    client = TrecoClient()
    try:
        await client.start(ticket_id)
        try:
            result = await do_work()
            await client.done(ticket_id, tokens_in=result.total_in, tokens_out=result.total_out)
        except Exception as exc:
            await client.error(ticket_id, str(exc))
            raise
    finally:
        await client.close()
```

### Pattern 3 — Long-running agent with manual heartbeats

If `track` is not suitable (e.g. the agent loops indefinitely), manage heartbeats manually:

```python
import asyncio
from treco import TrecoClient

async def run_loop(ticket_id: str) -> None:
    client = TrecoClient()
    try:
        await client.start(ticket_id)
        while True:
            work_unit = await fetch_next_task()
            if work_unit is None:
                break
            await process(work_unit)
            await client.heartbeat(ticket_id)
        await client.done(ticket_id)
    finally:
        await client.close()
```

---

## Event Types

All events are appended to the `agent_events` table, which is append-only — no updates, no deletes ever.

| Event type | Emitted by | Side effect on the backend |
|------------|------------|---------------------------|
| `ticket_started` | `start()` | Agent → `working`, `current_ticket_id` set, ticket → `in_progress` |
| `heartbeat` | `heartbeat()` | Updates `agent.last_seen_at` |
| `criterion_checked` | `check()` | Sets `criterion.done = True` on the ticket |
| `criterion_failed` | `fail_criterion()` | No mutation to the criterion |
| `log` | `log()` | Triggers deviation detection |
| `done` | `done()` | Agent → `idle`, `current_ticket_id` cleared, ticket → `done` |
| `error` | `error()` | Agent → `error`, `current_ticket_id` cleared |
| `pr_opened` | — | Not emitted by the SDK; use `_emit` directly if needed |
| `deviation` | Backend only | Set by the deviation detector, never by the agent |

---

## Error Handling

All public methods call `response.raise_for_status()` internally.

```python
import httpx
from treco import TrecoClient

client = TrecoClient()

try:
    await client.check(
        ticket_id,
        criterion_id="3f1ab0a1-318c-423f-88a7-a7c88703f93a",
        tokens_in=800,
        tokens_out=200,
    )
except httpx.HTTPStatusError as exc:
    # 401 — invalid or expired API key
    # 404 — ticket not found in this workspace
    # 422 — malformed request body (criterion_id format, unknown event_type)
    print(f"Treco backend error: {exc.response.status_code} {exc.response.text}")
except httpx.RequestError as exc:
    # DNS failure, connection refused, timeout (default: 10s)
    print(f"Treco network error: {exc}")
```

Heartbeat failures inside `track` are silently swallowed — a transient network error will not abort the agent session.

---

## Full Example

```python
import asyncio
from treco import TrecoClient

TICKET_ID            = "b2e3f1a0-4c87-4d1e-b581-2e0c3f1a9d44"
CRITERION_REGISTER   = "3f1ab0a1-318c-423f-88a7-a7c88703f93a"
CRITERION_CALLBACK   = "4f0a15d7-f9a5-4f7e-a49e-07d9190c4b5e"
CRITERION_TESTS_PASS = "9a2c84bb-1123-4e9a-bb30-f07c109d5e21"


async def main() -> None:
    client = TrecoClient()  # reads TRECO_API_KEY from environment
    try:
        async with client.track(TICKET_ID) as treco:

            await treco.log(TICKET_ID, "Registering OAuth app via GitHub API")
            reg = await register_github_oauth_app()
            await treco.check(
                TICKET_ID,
                criterion_id=CRITERION_REGISTER,
                tokens_in=reg.tokens_in,
                tokens_out=reg.tokens_out,
                model="claude-sonnet-4-6",
            )

            await treco.log(TICKET_ID, "Adding /auth/github/callback endpoint")
            cb = await add_callback_endpoint()
            await treco.check(
                TICKET_ID,
                criterion_id=CRITERION_CALLBACK,
                tokens_in=cb.tokens_in,
                tokens_out=cb.tokens_out,
                model="claude-sonnet-4-6",
            )

            await treco.log(TICKET_ID, "Running integration tests")
            tests = await run_tests()
            if tests.passed:
                await treco.check(TICKET_ID, criterion_id=CRITERION_TESTS_PASS)
            else:
                await treco.fail_criterion(
                    TICKET_ID,
                    criterion_id=CRITERION_TESTS_PASS,
                    reason=tests.failure_summary,
                )

    finally:
        await client.close()


asyncio.run(main())
```

---

## Related

- [CLI Reference](cli-reference.md) — `treco init`, `treco start`, `treco check`
- [Concepts](concepts.md) — workspaces, tickets, agents, events, criteria
- [Quickstart](quickstart.md) — zero to first agent reporting
- [SDK Reference](sdk-reference.md) — condensed method index
