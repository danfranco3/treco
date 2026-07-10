"""
Minimal stdio MCP server exposing `mark_criterion_done` to Claude Code.

Launched as a subprocess by Claude Code when passed via --mcp-config.
Reads JSON-RPC 2.0 from stdin, writes to stdout.
All Treco communication goes via env vars: TRECO_API_KEY, TRECO_URL, TRECO_TICKET_ID.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request


def _post(url: str, api_key: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Agent-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _reply(rid: object, result: object) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)


def _error(rid: object, code: int, msg: str) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}), flush=True)


_TOOLS = [
    {
        "name": "mark_criterion_done",
        "description": (
            "Mark an acceptance criterion as done. Call this after you complete each criterion. "
            "Include the file you changed and a short note."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "criterion_id": {
                    "type": "string",
                    "description": "The criterion ID from the task description",
                },
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path of the main file you changed",
                },
                "notes": {
                    "type": "string",
                    "description": "One sentence describing what you did",
                },
            },
            "required": ["criterion_id"],
        },
    }
]


def _handle(msg: dict) -> None:
    rid = msg.get("id")
    method = msg.get("method", "")

    if method == "initialize":
        _reply(rid, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "treco", "version": "1.0.0"},
        })
        return

    if method == "notifications/initialized":
        return

    if method == "tools/list":
        _reply(rid, {"tools": _TOOLS})
        return

    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        if name != "mark_criterion_done":
            _error(rid, -32601, f"Unknown tool: {name}")
            return

        api_key = os.environ.get("TRECO_API_KEY", "")
        base_url = os.environ.get("TRECO_URL", "http://localhost:8001")
        ticket_id = os.environ.get("TRECO_TICKET_ID", "")

        criterion_id = args.get("criterion_id", "")
        file_path = args.get("file_path")
        notes = args.get("notes")

        if not criterion_id:
            _error(rid, -32602, "criterion_id is required")
            return

        try:
            payload: dict = {"file_path": file_path, "notes": notes}
            _post(
                f"{base_url}/api/events",
                api_key,
                {
                    "ticket_id": ticket_id,
                    "event_type": "criterion_checked",
                    "criterion_id": criterion_id,
                    "payload": {k: v for k, v in payload.items() if v is not None},
                },
            )
            _reply(rid, {
                "content": [{"type": "text", "text": f"Criterion {criterion_id} marked done."}],
            })
        except Exception as exc:
            _error(rid, -32603, str(exc))
        return

    if rid is not None:
        _error(rid, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        _handle(msg)


if __name__ == "__main__":
    main()
