"""
treco CLI — track agent sessions from the terminal or Claude Code hooks.

Usage:
  treco init                        Interactive setup, writes ~/.treco
  treco start <ticket-id>           Start tracking a ticket
  treco check <criterion-id>        Mark a criterion done (uses active session)
  treco fail  <criterion-id>        Mark a criterion failed
  treco log   <message>             Log a message to the active ticket
  treco done                        End active session, mark ticket done
  treco status                      Show active session info

  treco hook post-tool-use          Called by Claude Code PostToolUse hook (reads stdin)
  treco hook stop                   Called by Claude Code Stop hook (reads stdin)
"""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

SESSION_FILE = Path.home() / ".treco_session"
CONFIG_FILE = Path.home() / ".treco"

# ── config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    CONFIG_FILE.chmod(0o600)


def load_session() -> dict:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    return {}


def save_session(s: dict) -> None:
    SESSION_FILE.write_text(json.dumps(s))


def clear_session() -> None:
    SESSION_FILE.unlink(missing_ok=True)


def require_session() -> dict:
    s = load_session()
    if not s.get("ticket_id"):
        print("No active session. Run: treco start <ticket-id>", file=sys.stderr)
        sys.exit(1)
    return s


def require_config() -> dict:
    cfg = load_config()
    api_key = cfg.get("api_key") or os.environ.get("TRECO_API_KEY")
    base_url = cfg.get("base_url") or os.environ.get("TRECO_URL", "http://localhost:8000")
    if not api_key:
        print("Not configured. Run: treco init", file=sys.stderr)
        sys.exit(1)
    return {"api_key": api_key, "base_url": base_url}


# ── HTTP ──────────────────────────────────────────────────────────────────────

async def post_event(cfg: dict, ticket_id: str, event_type: str, **kwargs) -> None:
    body = {"ticket_id": ticket_id, "event_type": event_type, **kwargs}
    body.setdefault("tokens_in", 0)
    body.setdefault("tokens_out", 0)
    body.setdefault("payload", {})
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(
            f"{cfg['base_url']}/api/events/",
            json=body,
            headers={"X-Agent-Key": cfg["api_key"]},
        )
        r.raise_for_status()


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_init():
    print("Treco setup")
    print("-----------")
    base_url = input("Treco URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    api_key = input("Agent API key: ").strip()
    if not api_key:
        print("API key required.", file=sys.stderr)
        sys.exit(1)
    save_config({"base_url": base_url, "api_key": api_key})
    print(f"Saved to {CONFIG_FILE}")


def cmd_start(ticket_id: str):
    cfg = require_config()
    asyncio.run(post_event(cfg, ticket_id, "ticket_started", payload={"source": "cli"}))
    save_session({"ticket_id": ticket_id, "tokens_in": 0, "tokens_out": 0})
    print(f"Started tracking ticket {ticket_id}")


def cmd_check(criterion_id: str):
    cfg = require_config()
    s = require_session()
    asyncio.run(post_event(cfg, s["ticket_id"], "criterion_checked", criterion_id=criterion_id))
    print(f"Criterion {criterion_id} checked")


def cmd_fail(criterion_id: str, reason: str = ""):
    cfg = require_config()
    s = require_session()
    asyncio.run(post_event(cfg, s["ticket_id"], "criterion_failed",
                           criterion_id=criterion_id, payload={"reason": reason}))
    print(f"Criterion {criterion_id} failed")


def cmd_log(message: str):
    cfg = require_config()
    s = require_session()
    asyncio.run(post_event(cfg, s["ticket_id"], "log", payload={"message": message}))


def cmd_done():
    cfg = require_config()
    s = require_session()
    asyncio.run(post_event(cfg, s["ticket_id"], "done",
                           tokens_in=s.get("tokens_in", 0),
                           tokens_out=s.get("tokens_out", 0)))
    clear_session()
    print(f"Session done. Ticket {s['ticket_id']} marked complete.")


def cmd_status():
    s = load_session()
    if not s.get("ticket_id"):
        print("No active session.")
    else:
        print(f"Ticket:     {s['ticket_id']}")
        print(f"Tokens in:  {s.get('tokens_in', 0):,}")
        print(f"Tokens out: {s.get('tokens_out', 0):,}")


# ── Claude Code hook handlers ──────────────────────────────────────────────────

def cmd_hook_post_tool_use():
    """
    Called by Claude Code PostToolUse hook.
    Reads hook JSON from stdin, accumulates token usage in session.
    """
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    s = load_session()
    if not s.get("ticket_id"):
        sys.exit(0)

    usage = payload.get("usage") or {}
    tokens_in = usage.get("input_tokens", 0)
    tokens_out = usage.get("output_tokens", 0)

    if tokens_in or tokens_out:
        s["tokens_in"] = s.get("tokens_in", 0) + tokens_in
        s["tokens_out"] = s.get("tokens_out", 0) + tokens_out
        save_session(s)

        cfg = require_config()
        tool_name = payload.get("tool_name", "")
        asyncio.run(post_event(
            cfg, s["ticket_id"], "log",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=payload.get("model"),
            payload={"message": f"tool: {tool_name}", "tool": tool_name},
        ))

    sys.exit(0)


def cmd_hook_stop():
    """
    Called by Claude Code Stop hook.
    Finalizes the session — posts done event with total tokens.
    """
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        payload = {}

    s = load_session()
    if not s.get("ticket_id"):
        sys.exit(0)

    usage = payload.get("usage") or {}
    s["tokens_in"] = s.get("tokens_in", 0) + usage.get("input_tokens", 0)
    s["tokens_out"] = s.get("tokens_out", 0) + usage.get("output_tokens", 0)

    cfg = load_config()
    api_key = cfg.get("api_key") or os.environ.get("TRECO_API_KEY", "")
    base_url = cfg.get("base_url") or os.environ.get("TRECO_URL", "http://localhost:8000")
    if not api_key:
        clear_session()
        sys.exit(0)

    asyncio.run(post_event(
        {"api_key": api_key, "base_url": base_url},
        s["ticket_id"], "done",
        tokens_in=s["tokens_in"],
        tokens_out=s["tokens_out"],
    ))
    clear_session()
    sys.exit(0)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "init":
        cmd_init()
    elif cmd == "start" and len(args) >= 2:
        cmd_start(args[1])
    elif cmd == "check" and len(args) >= 2:
        cmd_check(args[1])
    elif cmd == "fail" and len(args) >= 2:
        cmd_fail(args[1], " ".join(args[2:]))
    elif cmd == "log" and len(args) >= 2:
        cmd_log(" ".join(args[1:]))
    elif cmd == "done":
        cmd_done()
    elif cmd == "status":
        cmd_status()
    elif cmd == "hook" and len(args) >= 2:
        sub = args[1]
        if sub == "post-tool-use":
            cmd_hook_post_tool_use()
        elif sub == "stop":
            cmd_hook_stop()
        else:
            print(f"Unknown hook: {sub}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Unknown command: {cmd}\nRun 'treco --help' for usage.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
