# CLI Reference

Complete reference for the `treco` CLI. Install via:

```bash
pip install "treco[server]"
```

---

## Configuration

The CLI reads from `~/.treco/config.json` (chmod 600). Every key can be overridden by an environment variable.

| Config key | Env var | Default |
|---|---|---|
| `base_url` | `TRECO_URL` | `http://localhost:8001` |
| `api_key` | `TRECO_API_KEY` | — |
| `workspace_id` | `TRECO_WORKSPACE_ID` | — |
| `github_token` | — | — |
| `linear_api_key` | — | — |

Session state (active ticket, running token counts) is stored in `~/.treco_session`. Override path with `TRECO_SESSION_FILE`.

---

## Setup

### `treco init`

Interactive first-time setup. Creates or updates `~/.treco/config.json` and installs Claude Code hooks.

```
treco init
```

Prompts:
- **Treco URL** — backend address (default `http://localhost:8001`)
- **Workspace ID** — logical tenant namespace (default `demo`)

If the backend is unreachable, offers to start it via `treco server start`.

Calls `POST /api/init/` to create an agent record using the machine hostname. Returns an API key stored in config. The raw key is never shown again.

Exits 1 if an agent with the same hostname already exists in the workspace. To re-init: delete the agent from the dashboard or use a different workspace ID.

---

## Session commands

### `treco new [title]`

Create a ticket and optionally start a session.

```
treco new
treco new "Add dark mode toggle"
```

- If `title` is omitted, prompts interactively.
- Prompts for an optional description. Include `- [ ] criterion text` lines to auto-extract acceptance criteria via LLM.
- Prints the ticket ID and extracted criteria.
- Offers to start a session immediately (equivalent to running `treco start` then `treco inject`).

---

### `treco start [ticket-id]`

Begin tracking a ticket. Emits a `ticket_started` event and writes the active session to `~/.treco_session`.

```
treco start
treco start abc123
```

- If `ticket-id` is omitted, shows an interactive picker of open tickets.
- Offers to inject ticket context into the agent config file after starting.

---

### `treco status`

Show the active session.

```
treco status
```

Output:

```
Ticket:     abc123
Tokens in:  14,203
Tokens out: 3,841
```

Prints "No active session." if none exists.

---

### `treco done`

End the active session and mark the ticket complete.

```
treco done
```

Emits a `done` event with accumulated token counts from `~/.treco_session`, then clears the session file.

Exits 1 if no active session.

---

## Criteria commands

### `treco check <criterion-id>`

Mark an acceptance criterion as done.

```
treco check 3f1ab0a1
```

`criterion-id` is the `id` field on a criterion object (UUID or prefix). Shown by `treco new` and in the injected CLAUDE.md block.

Requires an active session. Emits a `criterion_checked` event.

---

### `treco fail <criterion-id> [reason]`

Mark an acceptance criterion as failed.

```
treco fail 3f1ab0a1
treco fail 3f1ab0a1 "API returns 500 on empty payload"
```

`reason` is appended to the event payload and visible in the dashboard. Optional.

Requires an active session. Emits a `criterion_failed` event.

---

### `treco log <message>`

Append a log message to the active ticket's event stream.

```
treco log "Refactored auth middleware, tests passing"
```

Emits a `log` event. Visible in the dashboard event timeline.

Requires an active session.

---

## Import commands

### `treco import <url>`

Import a single issue from GitHub or Linear by URL.

```
treco import https://github.com/owner/repo/issues/42
treco import https://linear.app/team/issue/ENG-99/fix-auth-bug
```

- GitHub: prompts for a PAT (repo scope) if not cached in config.
- Linear: prompts for an API key if not cached in config.
- Tokens are saved to `~/.treco/config.json` after first use.
- Offers to start a session on the imported ticket.

---

### `treco connect github`

Bulk-import up to 20 open GitHub issues into the workspace.

```
treco connect github
```

Prompts:
1. **GitHub PAT** — token with `repo` scope (cached after first use)
2. **Repository** — `owner/repo` format

Fetches open issues from the GitHub API via the backend, then confirms before importing.

---

### `treco connect linear`

Bulk-import up to 20 open Linear issues into the workspace.

```
treco connect linear
```

Prompts:
1. **Linear API Key** — cached after first use
2. **Team key** — e.g. `ENG` (optional; blank imports all teams)

---

## Inject

### `treco inject [ticket-id]`

Write the active ticket's context (title, criteria, env hints) into the agent's config file.

```
treco inject
treco inject abc123
```

- If `ticket-id` is omitted, uses the active session.
- Auto-detects the agent environment and writes to the appropriate file:

| Agent | Target file |
|---|---|
| Claude Code | `CLAUDE.md` in CWD |
| Cursor | `.cursor/rules/treco-ticket.mdc` |
| Windsurf | `.windsurfrules` |
| VS Code Copilot | `.github/copilot-instructions.md` |
| Terminal (fallback) | stdout |

For Claude Code, replaces any existing `## Active Treco Ticket` section. For Cursor, rewrites the file with `alwaysApply: true` frontmatter.

---

## Server commands

### `treco server start [--port N]`

Start the Treco backend as a background daemon.

```
treco server start
treco server start --port 9000
```

- Requires `pip install "treco[server]"` (pulls in `uvicorn`).
- PID stored in `~/.treco/server.pid`.
- Backend directory resolved automatically from the installed package. Override with `TRECO_BACKEND_DIR`.
- Dashboard at `http://localhost:8001`, API docs at `http://localhost:8001/docs`.

---

### `treco server stop`

Stop the background daemon.

```
treco server stop
```

Sends SIGTERM to the PID in `~/.treco/server.pid`.

---

### `treco server status`

Print whether the server is running.

```
treco server status
```

Output: `Running (PID 12345)` or `Not running`.

---

## Hook commands

These are called automatically by Claude Code hooks. Run `treco hook install` once during setup — `treco init` does this for you.

### `treco hook install`

Register Treco hooks in `~/.claude/settings.json`.

```
treco hook install
```

Installs two hooks:
- `PostToolUse` — updates token counts and logs tool activity after each Claude tool call
- `Stop` — flushes final token counts and emits a `done` event when the Claude session ends

Safe to run multiple times (idempotent).

---

### `treco hook post-tool-use`

**Called automatically by Claude Code.** Do not invoke manually.

Reads a JSON payload from stdin (Claude's PostToolUse hook format). Accumulates `tokens_in` / `tokens_out` in the session file and emits a `log` event with tool name and file/command detail.

Cache-read tokens are excluded from `tokens_in` to avoid inflated cost reporting.

---

### `treco hook stop`

**Called automatically by Claude Code.** Do not invoke manually.

Reads a JSON payload from stdin (Claude's Stop hook format). Flushes final token totals, emits a `done` event, and clears the session file.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | User error (missing arg, no session, backend unreachable, auth failure) |

Hook commands (`post-tool-use`, `stop`) always exit 0 — they must not crash the agent's shell.

---

## Common workflows

**First time setup:**
```bash
treco server start
treco init
treco connect github   # or: treco import <url>
treco start
```

**During an agent session:**
```bash
treco status                        # check active ticket
treco check 3f1ab0a1               # criterion done
treco fail 4f0a15d7 "blocked"      # criterion failed
treco log "switched approach"      # freeform note
treco done                          # end session
```

**New ticket from scratch:**
```bash
treco new "Implement rate limiting"
# enter description with - [ ] criteria lines
# accept prompt to start session
```
