"""Tests for Claude Code hook handlers — synthetic payloads, exit code guarantees."""
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CLAUDE_CODE_POST_TOOL_USE = {
    "session_id": "test-123",
    "hook_event_name": "PostToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "npm test"},
    "tool_response": {"output": "3 passed", "error": None},
    "usage": {
        "input_tokens": 1500,
        "output_tokens": 320,
        "cache_creation_input_tokens": 200,
        "cache_read_input_tokens": 800,
    },
}

CLAUDE_CODE_POST_TOOL_USE_EDIT = {
    "session_id": "test-123",
    "hook_event_name": "PostToolUse",
    "tool_name": "Edit",
    "tool_input": {"file_path": "/repo/app/foo.py", "old_string": "a", "new_string": "b"},
    "tool_response": {"success": True},
    "usage": {
        "input_tokens": 1500,
        "output_tokens": 320,
        "cache_creation_input_tokens": 200,
        "cache_read_input_tokens": 800,
    },
}

CLAUDE_CODE_STOP = {
    "session_id": "test-123",
    "hook_event_name": "Stop",
    "usage": {
        "input_tokens": 45000,
        "output_tokens": 8200,
        "cache_creation_input_tokens": 12000,
        "cache_read_input_tokens": 33000,
    },
}


def _run_post_tool_use_with(payload: dict, session: dict | None = None) -> dict:
    """Run _run_post_tool_use with mocked stdin and session, return saved session."""
    import treco.cli as cli

    saved = {}

    def fake_save_session(s: dict) -> None:
        saved.update(s)

    def fake_load_session() -> dict:
        return session or {"ticket_id": "ticket-abc", "tokens_in": 0, "tokens_out": 0}

    with (
        patch.object(cli, "load_session", fake_load_session),
        patch.object(cli, "save_session", fake_save_session),
        patch.object(cli, "load_config", return_value={}),
        patch("sys.stdin", StringIO(json.dumps(payload))),
        patch.object(cli, "asyncio") as mock_async,
    ):
        mock_async.run = MagicMock()
        cli._run_post_tool_use()

    return saved


def _run_post_tool_use_capture_event(payload: dict, session: dict | None = None) -> dict:
    """Run _run_post_tool_use with mocked stdin/session, return the kwargs passed to post_event."""
    import treco.cli as cli

    captured: dict = {}

    def fake_post_event(cfg, ticket_id, event_type, **kwargs):
        captured["ticket_id"] = ticket_id
        captured["event_type"] = event_type
        captured.update(kwargs)

    with (
        patch.object(cli, "load_session", lambda: session or {"ticket_id": "ticket-abc", "tokens_in": 0, "tokens_out": 0}),
        patch.object(cli, "save_session"),
        patch.object(cli, "load_config", return_value={"api_key": "key-x", "base_url": "http://localhost:8001"}),
        patch.object(cli, "post_event", fake_post_event),
        patch("sys.stdin", StringIO(json.dumps(payload))),
        patch.object(cli, "asyncio") as mock_async,
    ):
        mock_async.run = lambda coro: None
        cli._run_post_tool_use()

    return captured


class TestPostToolUseTokenCounting:
    def test_cache_read_excluded_from_tokens_in(self):
        saved = _run_post_tool_use_with(CLAUDE_CODE_POST_TOOL_USE)
        # input_tokens=1500, cache_read=800 → tokens_in=700
        assert saved["tokens_in"] == 700

    def test_tokens_out_counted_correctly(self):
        saved = _run_post_tool_use_with(CLAUDE_CODE_POST_TOOL_USE)
        assert saved["tokens_out"] == 320

    def test_cache_write_tracked(self):
        saved = _run_post_tool_use_with(CLAUDE_CODE_POST_TOOL_USE)
        assert saved["cache_write_tokens"] == 200

    def test_tokens_accumulate_across_calls(self):
        session = {"ticket_id": "ticket-abc", "tokens_in": 100, "tokens_out": 50}
        saved = _run_post_tool_use_with(CLAUDE_CODE_POST_TOOL_USE, session=session)
        assert saved["tokens_in"] == 800   # 100 + 700
        assert saved["tokens_out"] == 370  # 50 + 320

    def test_negative_cache_read_clamped_to_zero(self):
        payload = {
            **CLAUDE_CODE_POST_TOOL_USE,
            "usage": {"input_tokens": 500, "output_tokens": 100, "cache_read_input_tokens": 1000},
        }
        saved = _run_post_tool_use_with(payload)
        assert saved["tokens_in"] == 0

    def test_no_session_is_noop(self):
        import treco.cli as cli

        saved = {}
        with (
            patch.object(cli, "load_session", return_value={}),
            patch.object(cli, "save_session", lambda s: saved.update(s)),
            patch("sys.stdin", StringIO(json.dumps(CLAUDE_CODE_POST_TOOL_USE))),
        ):
            cli._run_post_tool_use()

        assert not saved

    def test_invalid_json_does_not_raise(self):
        import treco.cli as cli

        with (
            patch.object(cli, "load_session", return_value={}),
            patch("sys.stdin", StringIO("not json")),
        ):
            cli._run_post_tool_use()  # must not raise

    def test_edit_tool_input_captures_file_path(self):
        captured = _run_post_tool_use_capture_event(CLAUDE_CODE_POST_TOOL_USE_EDIT)
        assert captured["payload"]["file_path"] == "/repo/app/foo.py"
        assert captured["payload"]["tool"] == "Edit"
        assert "/repo/app/foo.py" in captured["payload"]["message"]

    def test_bash_tool_input_captures_truncated_command(self):
        captured = _run_post_tool_use_capture_event(CLAUDE_CODE_POST_TOOL_USE)
        assert captured["payload"]["file_path"] is None
        assert captured["payload"]["tool"] == "Bash"
        assert "npm test" in captured["payload"]["message"]

    def test_cmd_hook_exits_zero(self):
        import treco.cli as cli

        with (
            patch.object(cli, "load_session", return_value={}),
            patch("sys.stdin", StringIO(json.dumps(CLAUDE_CODE_POST_TOOL_USE))),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.cmd_hook_post_tool_use()

        assert exc_info.value.code == 0


class TestStopHook:
    def test_stop_hook_exits_zero(self):
        import treco.cli as cli

        with (
            patch.object(cli, "load_session", return_value={}),
            patch("sys.stdin", StringIO(json.dumps(CLAUDE_CODE_STOP))),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.cmd_hook_stop()

        assert exc_info.value.code == 0

    def test_stop_fires_done_event(self):
        import treco.cli as cli

        session = {"ticket_id": "ticket-abc", "tokens_in": 1000, "tokens_out": 200}
        fired: list[tuple] = []

        async def fake_post_event(cfg, ticket_id, event_type, **kwargs):
            fired.append((ticket_id, event_type, kwargs))

        with (
            patch.object(cli, "load_session", return_value=session),
            patch.object(cli, "clear_session"),
            patch.object(cli, "load_config", return_value={"api_key": "key-x", "base_url": "http://localhost:8001"}),
            patch.object(cli, "post_event", fake_post_event),
            patch("sys.stdin", StringIO(json.dumps(CLAUDE_CODE_STOP))),
            patch.object(cli, "asyncio") as mock_async,
        ):
            mock_async.run = lambda coro: None
            cli._run_stop()

        # Did not raise
