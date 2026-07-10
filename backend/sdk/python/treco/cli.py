"""
treco CLI — track agent sessions from the terminal or Claude Code hooks.

Usage:
  treco init                        Interactive setup, writes ~/.treco/config.json
  treco new [title]                 Create a new ticket (prompts if no title given)
  treco refine [ticket-id]          Ask AI to propose acceptance criteria + test commands
  treco start [ticket-id]           Start tracking a ticket (picker if no id given)
  treco check <criterion-id>        Mark a criterion done — runs test command if set
  treco log   <message>             Log a message to the active ticket
  treco done                        End active session, mark ticket done
  treco status                      Show active session info
  treco inject [ticket-id]          Write ticket context into the active agent config

  treco hook post-tool-use          Called by Claude Code PostToolUse hook (reads stdin)
  treco hook stop                   Called by Claude Code Stop hook (reads stdin)
  treco hook install                Install Claude Code hooks into ~/.claude/settings.json
"""

import asyncio
import json
import os
import re
import socket
import sys
from pathlib import Path

import httpx

CONFIG_DIR = Path.home() / ".treco"
CONFIG_FILE = Path(os.environ.get("TRECO_CONFIG_FILE", str(CONFIG_DIR / "config.json")))
SESSION_FILE = Path(os.environ.get("TRECO_SESSION_FILE", str(Path.home() / ".treco_session")))

# ── config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
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
        # Fall back to env var (set by implement runner subprocess)
        ticket_id = os.environ.get("TRECO_TICKET_ID")
        if ticket_id:
            return {"ticket_id": ticket_id}
        print("No active session. Run: treco start", file=sys.stderr)
        sys.exit(1)
    return s


def require_config() -> dict:
    cfg = load_config()
    api_key = cfg.get("api_key") or os.environ.get("TRECO_API_KEY")
    base_url = cfg.get("base_url") or os.environ.get("TRECO_URL", "http://localhost:8001")
    if not api_key:
        print("Not configured. Run: treco init", file=sys.stderr)
        sys.exit(1)
    return {"api_key": api_key, "base_url": base_url}


def _workspace_id() -> str:
    cfg = load_config()
    wid = cfg.get("workspace_id") or os.environ.get("TRECO_WORKSPACE_ID", "")
    if not wid:
        wid = input("Workspace ID: ").strip()
        if not wid:
            print("Workspace ID required.", file=sys.stderr)
            sys.exit(1)
        cfg["workspace_id"] = wid
        save_config(cfg)
    return wid


# ── HTTP ──────────────────────────────────────────────────────────────────────

async def post_event(cfg: dict, ticket_id: str, event_type: str, **kwargs) -> None:
    body = {"ticket_id": ticket_id, "event_type": event_type, **kwargs}
    body.setdefault("tokens_in", 0)
    body.setdefault("tokens_out", 0)
    body.setdefault("payload", {})
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(
            f"{cfg['base_url']}/api/events",
            json=body,
            headers={"X-Agent-Key": cfg["api_key"]},
        )
        r.raise_for_status()


async def post_json(base_url: str, path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{base_url}{path}", json=body)
        r.raise_for_status()
        return r.json()


# ── hooks ─────────────────────────────────────────────────────────────────────

def _install_hooks() -> None:
    settings_path = Path.home() / ".claude" / "settings.json"
    hook_entry = {"type": "command", "command": "treco hook post-tool-use"}
    stop_entry = {"type": "command", "command": "treco hook stop"}

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except Exception:
            data = {}
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    hooks = data.setdefault("hooks", {})

    post_tool_hooks = hooks.setdefault("PostToolUse", [])
    post_tool_matcher = next((h for h in post_tool_hooks if h.get("matcher") == ""), None)
    if post_tool_matcher is None:
        post_tool_matcher = {"matcher": "", "hooks": []}
        post_tool_hooks.append(post_tool_matcher)
    inner = post_tool_matcher.setdefault("hooks", [])
    if hook_entry not in inner:
        inner.append(hook_entry)

    stop_hooks = hooks.setdefault("Stop", [])
    stop_matcher = next((h for h in stop_hooks if stop_entry in h.get("hooks", [])), None)
    if stop_matcher is None:
        stop_hooks.append({"hooks": [stop_entry]})

    settings_path.write_text(json.dumps(data, indent=2))
    print(f"Hooks installed in {settings_path}")


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_init():
    print("Treco setup")
    print("-----------")
    base_url = input("Treco URL [http://localhost:8001]: ").strip() or "http://localhost:8001"
    workspace_id = input("Workspace ID [demo]: ").strip() or "demo"

    try:
        httpx.get(f"{base_url}/api/tickets?workspace_id={workspace_id}", timeout=2.0)
    except Exception:
        print("Backend not reachable. Start it manually: uvicorn app.main:app --port 8001", file=sys.stderr)

    try:
        r = httpx.post(
            f"{base_url}/api/init/",
            json={"workspace_id": workspace_id, "agent_name": socket.gethostname()},
            timeout=5.0,
        )
        r.raise_for_status()
        data = r.json()
        api_key = data["api_key"]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            print(
                f"Agent '{socket.gethostname()}' already exists in workspace '{workspace_id}'.\n"
                "To re-init, delete the existing agent or use a different workspace ID.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Error creating agent: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to connect to backend: {exc}", file=sys.stderr)
        sys.exit(1)

    save_config({"base_url": base_url, "api_key": api_key, "workspace_id": workspace_id})
    print(f"Saved to {CONFIG_FILE}")

    _install_hooks()

    print("\nSetup complete.")
    print(f"  Agent: {socket.gethostname()} in workspace '{workspace_id}'")
    print(f"  Backend: {base_url}")
    print(f"  Dashboard: {base_url}  (if server is running)")
    print("  Claude Code hooks installed")
    print("\nNext steps:")
    print("  treco new        — create a ticket")
    print("  treco start      — start tracking")


def cmd_new(title: str = ""):
    cfg = require_config()
    if not title:
        title = input("Ticket title: ").strip()
    if not title:
        print("Title required.", file=sys.stderr)
        sys.exit(1)
    description = input("Description (enter to skip): ").strip()

    workspace_id = _workspace_id()
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{cfg['base_url']}/api/tickets",
            json={"workspace_id": workspace_id, "title": title, "description": description or None},
            headers={"X-Agent-Key": cfg["api_key"]},
        )
        r.raise_for_status()
        ticket = r.json()

    ticket_id = ticket["id"]
    criteria: list[dict] = ticket.get("acceptance_criteria") or []

    print(f"\nCreated ticket {ticket_id}: {ticket['title']}")
    if criteria:
        print("Acceptance criteria:")
        for i, c in enumerate(criteria, 1):
            mark = "[x]" if c.get("done") else "[ ]"
            print(f"  {i}. {mark} {c['text']}  (id: {c['id'][:8]})")
    else:
        print("No acceptance criteria extracted (add a description with '- [ ] criteria' to auto-extract).")

    answer = input("\nStart a session now? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        _do_start(cfg, ticket_id)
        cmd_inject(ticket_id, criteria)


def cmd_refine(ticket_id: str = ""):
    cfg = require_config()
    if not ticket_id:
        ticket_id = _pick_ticket(cfg)
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{cfg['base_url']}/api/tickets/{ticket_id}/refine",
            json={},
            headers={"X-Agent-Key": cfg["api_key"]},
        )
        r.raise_for_status()
        ticket = r.json()

    criteria = ticket.get("acceptance_criteria") or []
    if not criteria:
        print("No criteria proposed — add a description to the ticket first.")
        return

    print(f"\nProposed criteria for: {ticket['title']}")
    print("─" * 60)
    for i, c in enumerate(criteria, 1):
        mark = "[✓]" if c.get("done") else "[ ]"
        print(f"  {i}. {mark} {c['text']}")
        if c.get("test_cmd"):
            print(f"       test: {c['test_cmd']}")
    print("─" * 60)
    print(f"\nEdit or approve in the UI. Ticket: {cfg['base_url']}/tickets/{ticket_id}")


def cmd_start(ticket_id: str = ""):
    cfg = require_config()
    if not ticket_id:
        ticket_id = _pick_ticket(cfg)
    _do_start(cfg, ticket_id)
    answer = input("Inject ticket context into agent config? [Y/n]: ").strip().lower()
    if answer not in ("n", "no"):
        cmd_inject(ticket_id)


def _do_start(cfg: dict, ticket_id: str) -> None:
    asyncio.run(post_event(cfg, ticket_id, "ticket_started", payload={"source": "cli"}))
    save_session({"ticket_id": ticket_id, "tokens_in": 0, "tokens_out": 0})
    print(f"Started tracking ticket {ticket_id}")


def _pick_ticket(cfg: dict) -> str:
    workspace_id = _workspace_id()
    with httpx.Client(timeout=8.0) as client:
        r = client.get(
            f"{cfg['base_url']}/api/tickets",
            params={"workspace_id": workspace_id},
            headers={"X-Agent-Key": cfg["api_key"]},
        )
        r.raise_for_status()
        tickets = r.json()

    open_tickets = [t for t in tickets if t.get("status") != "done"]
    if not open_tickets:
        print("No open tickets. Create one with: treco new")
        sys.exit(0)

    divider = "─" * 60
    print(f"\nOpen tickets:\n{divider}")
    for i, t in enumerate(open_tickets, 1):
        criteria = t.get("acceptance_criteria") or []
        done = sum(1 for c in criteria if c.get("done"))
        total = len(criteria)
        sid = t.get("source_id") or "custom"
        print(f"  {i:<3} [{sid:<12}]  {t['title'][:38]:<38}  ({done}/{total})")
    print(divider)

    raw = input("Pick [1]: ").strip() or "1"
    try:
        choice = int(raw)
    except ValueError:
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)
    if not (1 <= choice <= len(open_tickets)):
        print("Selection out of range.", file=sys.stderr)
        sys.exit(1)
    return open_tickets[choice - 1]["id"]


def cmd_check(criterion_id: str, file_path: str | None = None, notes: str | None = None):
    cfg = require_config()
    s = require_session()
    payload: dict = {}
    if file_path:
        payload["file_path"] = file_path
    if notes:
        payload["notes"] = notes
    asyncio.run(post_event(cfg, s["ticket_id"], "criterion_checked",
                           criterion_id=criterion_id, payload=payload))
    print(f"Criterion {criterion_id} checked")


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


# ── inject ────────────────────────────────────────────────────────────────────

def detect_agent(env: dict) -> str:
    if "CLAUDE_CODE" in env or Path.cwd().joinpath(".claude").exists():
        return "claude-code"
    if "CURSOR_TRACE_ID" in env or "CURSOR_SESSION" in env or Path.cwd().joinpath(".cursor").exists():
        return "cursor"
    if env.get("TERM_PROGRAM") == "vscode" or "VSCODE_PID" in env:
        return "vscode"
    if "CODEIUM_API_KEY" in env or Path.cwd().joinpath(".windsurfrules").exists():
        return "windsurf"
    return "terminal"


def _build_criteria_block(criteria: list[dict]) -> str:
    lines = []
    for c in criteria:
        mark = "x" if c.get("done") else " "
        lines.append(f"- [{mark}] {c['text']}  <!-- id: {c.get('id', '')} -->")
    return "\n".join(lines)


def _ticket_section(ticket: dict, criteria: list[dict]) -> str:
    source_id = ticket.get("source_id") or ticket.get("id", "")
    return (
        "## Active Treco Ticket\n"
        f"**[{source_id}] {ticket.get('title', '')}**  \n"
        "Session: `treco status` | Done: `treco done` | Check: `treco check <id>`\n\n"
        "Acceptance criteria:\n"
        f"{_build_criteria_block(criteria)}\n"
    )


def _replace_or_append(existing: str, header: str, section: str) -> str:
    pattern = re.compile(rf"(^|\n){re.escape(header)}\n.*?(?=\n## |\Z)", re.DOTALL)
    updated, n = pattern.subn(f"\n{section}", existing)
    if n:
        return updated.lstrip("\n")
    sep = "\n\n" if existing and not existing.endswith("\n\n") else ""
    return existing + sep + section


def _env_hints_block(cfg: dict) -> str:
    base_url = cfg.get("base_url", "http://localhost:8001")
    workspace_id = cfg.get("workspace_id", "demo")
    return (
        "<!-- treco-env\n"
        f"TRECO_URL={base_url}\n"
        f"TRECO_WORKSPACE_ID={workspace_id}\n"
        "(API key stored in ~/.treco/config.json — loaded automatically by `treco` CLI)\n"
        "-->"
    )


def cmd_inject(ticket_id: str = "", criteria: list[dict] | None = None):
    cfg = require_config()
    if not ticket_id:
        ticket_id = require_session()["ticket_id"]

    with httpx.Client(timeout=8.0) as client:
        r = client.get(f"{cfg['base_url']}/api/tickets/{ticket_id}",
                       headers={"X-Agent-Key": cfg["api_key"]})
        r.raise_for_status()
        ticket = r.json()

    if criteria is None:
        criteria = ticket.get("acceptance_criteria") or []

    agent = detect_agent(dict(os.environ))
    section = _ticket_section(ticket, criteria) + "\n" + _env_hints_block(cfg) + "\n"

    targets = {
        "claude-code": Path.cwd() / "CLAUDE.md",
        "cursor":      Path.cwd() / ".cursor" / "rules" / "treco-ticket.mdc",
        "windsurf":    Path.cwd() / ".windsurfrules",
        "vscode":      Path.cwd() / ".github" / "copilot-instructions.md",
    }

    if agent == "terminal":
        print(section)
        return

    target = targets[agent]
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text() if target.exists() else ""

    if agent == "cursor":
        content = "---\nalwaysApply: true\n---\n" + section
        target.write_text(content)
    else:
        target.write_text(_replace_or_append(existing, "## Active Treco Ticket", section))

    print(f"Injected into {target}")


# ── Claude Code hook handlers ─────────────────────────────────────────────────

def _safe_hook(fn):
    try:
        fn()
    except Exception:
        pass
    sys.exit(0)


def _run_post_tool_use():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return

    s = load_session()
    if not s.get("ticket_id"):
        return

    usage = payload.get("usage") or {}
    tokens_in = max(
        usage.get("input_tokens", 0) - usage.get("cache_read_input_tokens", 0),
        0,
    )
    tokens_out = usage.get("output_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)

    s["tokens_in"] = s.get("tokens_in", 0) + tokens_in
    s["tokens_out"] = s.get("tokens_out", 0) + tokens_out
    s["cache_write_tokens"] = s.get("cache_write_tokens", 0) + cache_write
    save_session(s)

    if tokens_in > 0 or tokens_out > 0:
        cfg = load_config()
        api_key = cfg.get("api_key") or os.environ.get("TRECO_API_KEY", "")
        base_url = cfg.get("base_url") or os.environ.get("TRECO_URL", "http://localhost:8001")
        if not api_key:
            return

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {}) or {}
        file_path = tool_input.get("file_path")
        command = tool_input.get("command", "")
        if tool_name == "Bash" and command:
            command = command[:120]
        detail = file_path or command
        asyncio.run(post_event(
            {"api_key": api_key, "base_url": base_url},
            s["ticket_id"], "log",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=payload.get("model"),
            payload={
                "tool": tool_name,
                "file_path": file_path,
                "message": f"{tool_name}: {detail}"[:200],
            },
        ))


def cmd_hook_post_tool_use():
    _safe_hook(_run_post_tool_use)


def _run_stop():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        payload = {}

    s = load_session()
    if not s.get("ticket_id"):
        return

    usage = payload.get("usage") or {}
    final_in = s.get("tokens_in", 0) + max(
        usage.get("input_tokens", 0) - usage.get("cache_read_input_tokens", 0),
        0,
    )
    final_out = s.get("tokens_out", 0) + usage.get("output_tokens", 0)

    cfg = load_config()
    api_key = cfg.get("api_key") or os.environ.get("TRECO_API_KEY", "")
    base_url = cfg.get("base_url") or os.environ.get("TRECO_URL", "http://localhost:8001")

    if api_key:
        asyncio.run(post_event(
            {"api_key": api_key, "base_url": base_url},
            s["ticket_id"], "done",
            tokens_in=final_in,
            tokens_out=final_out,
        ))
    clear_session()


def cmd_hook_stop():
    _safe_hook(_run_stop)


def cmd_hook_install():
    _install_hooks()


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "init":
        cmd_init()
    elif cmd == "new":
        cmd_new(" ".join(args[1:]))
    elif cmd == "refine":
        cmd_refine(args[1] if len(args) >= 2 else "")
    elif cmd == "start":
        cmd_start(args[1] if len(args) >= 2 else "")
    elif cmd == "check" and len(args) >= 2:
        import argparse as _ap
        _p = _ap.ArgumentParser()
        _p.add_argument("criterion_id")
        _p.add_argument("--file", dest="file_path", default=None)
        _p.add_argument("--notes", default=None)
        _opts = _p.parse_args(args[1:])
        cmd_check(_opts.criterion_id, file_path=_opts.file_path, notes=_opts.notes)
    elif cmd == "log" and len(args) >= 2:
        cmd_log(" ".join(args[1:]))
    elif cmd == "done":
        cmd_done()
    elif cmd == "status":
        cmd_status()
    elif cmd == "inject":
        cmd_inject(args[1] if len(args) >= 2 else "")
    elif cmd == "hook" and len(args) >= 2:
        {
            "post-tool-use": cmd_hook_post_tool_use,
            "stop": cmd_hook_stop,
            "install": cmd_hook_install,
        }.get(
            args[1], lambda: print(f"Unknown hook: {args[1]}", file=sys.stderr) or sys.exit(1)
        )()
    else:
        print(f"Unknown command: {cmd}\nRun 'treco --help' for usage.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
