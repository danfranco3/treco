# Claude Code Integration

Treco tracks Claude Code sessions ticket-by-ticket. Token usage, tool calls, and
session end are captured automatically via Claude Code hooks.

## Setup (one time)

```bash
pip install treco
treco init          # enter your Treco URL + agent API key
```

## Start a session

Before you start a Claude Code session on a ticket:

```bash
treco start <ticket-id>
```

Then run Claude Code normally. Treco accumulates token usage in the background.
When Claude Code finishes, it automatically posts a `done` event with totals.

## Wire up hooks (one time)

Add to your project's `.claude/settings.json` (or `~/.claude/settings.json` for global):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "treco hook post-tool-use"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "treco hook stop"
          }
        ]
      }
    ]
  }
}
```

`PostToolUse` fires after every tool call — Treco reads the `usage` field and
accumulates tokens. `Stop` fires when Claude Code exits — Treco posts the
final `done` event with total token counts and clears the session.

## Mark acceptance criteria from Claude Code

Inside your Claude Code session, you can call the CLI directly:

```bash
treco check <criterion-id>      # criterion done
treco fail  <criterion-id>      # criterion failed
treco log   "deployed to staging"
```

Or have your agent call the Treco API directly via the Python SDK.

## Environment variable override

If you don't want to run `treco init`, set env vars instead:

```bash
export TRECO_API_KEY=treco_...
export TRECO_URL=http://localhost:8000
```

## Multiple agents / parallel sessions

Each agent has its own API key. Run `treco start` in separate terminals with
different keys set via `TRECO_API_KEY`. Sessions are stored per-process in
`~/.treco_session` — if running parallel agents on the same machine, set
`TRECO_SESSION_FILE` to a unique path per agent (coming in v0.2).

## Using from any other framework

The Python SDK works with any agent — LangChain, CrewAI, AutoGen, custom:

```python
from treco import TrecoClient

client = TrecoClient(api_key="treco_...", base_url="http://localhost:8000")

async with client.track("ticket-id") as t:
    # your agent work here
    await t.check("ticket-id", criterion_id="crit-uuid-1", tokens_in=1200, tokens_out=400)
    await t.log("ticket-id", "opened PR #42", payload={"url": "https://github.com/..."})
```
