"""CLI command tests — config/session hygiene, event emission, ticket flows.

HTTP is intercepted with respx against the real request shapes the backend
expects; config/session files live in tmp_path via module-attribute patching.
"""
import json
from unittest.mock import patch

import pytest
import respx
from httpx import Response

import treco.cli as cli

BASE = "http://localhost:8001"


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cli, "SESSION_FILE", tmp_path / "session.json")
    monkeypatch.delenv("TRECO_API_KEY", raising=False)
    monkeypatch.delenv("TRECO_TICKET_ID", raising=False)
    monkeypatch.delenv("TRECO_WORKSPACE_ID", raising=False)
    return tmp_path


@pytest.fixture
def configured():
    cli.save_config({"base_url": BASE, "api_key": "treco_cli_key", "workspace_id": "ws1"})


class TestConfigFile:
    def test_save_config_written_chmod_600(self):
        cli.save_config({"api_key": "secret"})
        mode = cli.CONFIG_FILE.stat().st_mode & 0o777
        assert mode == 0o600

    def test_load_config_round_trips(self):
        cli.save_config({"api_key": "k", "base_url": BASE})
        assert cli.load_config() == {"api_key": "k", "base_url": BASE}

    def test_corrupt_config_returns_empty_dict(self):
        cli.CONFIG_FILE.write_text("{broken")
        assert cli.load_config() == {}

    def test_require_config_exits_when_unconfigured(self):
        with pytest.raises(SystemExit) as exc:
            cli.require_config()
        assert exc.value.code == 1

    def test_require_config_falls_back_to_env_key(self, monkeypatch):
        monkeypatch.setenv("TRECO_API_KEY", "treco_env_key")
        cfg = cli.require_config()
        assert cfg["api_key"] == "treco_env_key"


class TestSessionFile:
    def test_session_round_trips(self):
        cli.save_session({"ticket_id": "t1", "tokens_in": 5})
        assert cli.load_session()["ticket_id"] == "t1"

    def test_clear_session_removes_file(self):
        cli.save_session({"ticket_id": "t1"})
        cli.clear_session()
        assert cli.load_session() == {}

    def test_clear_session_idempotent(self):
        cli.clear_session()
        cli.clear_session()

    def test_require_session_exits_without_session(self):
        with pytest.raises(SystemExit):
            cli.require_session()

    def test_require_session_falls_back_to_runner_env(self, monkeypatch):
        monkeypatch.setenv("TRECO_TICKET_ID", "env-ticket")
        assert cli.require_session() == {"ticket_id": "env-ticket"}


class TestStartAndCheck:
    @respx.mock
    def test_do_start_posts_ticket_started_and_saves_session(self, configured):
        route = respx.post(f"{BASE}/api/events").mock(
            return_value=Response(200, json={"id": "e1"})
        )
        cli._do_start(cli.require_config(), "ticket-42")
        body = json.loads(route.calls[0].request.content)
        assert body["event_type"] == "ticket_started"
        assert body["ticket_id"] == "ticket-42"
        assert route.calls[0].request.headers["x-agent-key"] == "treco_cli_key"
        assert cli.load_session()["ticket_id"] == "ticket-42"

    @respx.mock
    def test_check_posts_criterion_checked_with_metadata(self, configured):
        cli.save_session({"ticket_id": "ticket-42"})
        route = respx.post(f"{BASE}/api/events").mock(
            return_value=Response(200, json={"id": "e2"})
        )
        cli.cmd_check("crit-1", file_path="src/x.py", notes="done it")
        body = json.loads(route.calls[0].request.content)
        assert body["event_type"] == "criterion_checked"
        assert body["criterion_id"] == "crit-1"
        assert body["payload"] == {"file_path": "src/x.py", "notes": "done it"}

    @respx.mock
    def test_done_posts_session_tokens_and_clears_session(self, configured):
        cli.save_session({"ticket_id": "ticket-42", "tokens_in": 123, "tokens_out": 45})
        route = respx.post(f"{BASE}/api/events").mock(
            return_value=Response(200, json={"id": "e3"})
        )
        cli.cmd_done()
        body = json.loads(route.calls[0].request.content)
        assert body["event_type"] == "done"
        assert body["tokens_in"] == 123
        assert body["tokens_out"] == 45
        assert cli.load_session() == {}

    @respx.mock
    def test_log_posts_message(self, configured):
        cli.save_session({"ticket_id": "ticket-42"})
        route = respx.post(f"{BASE}/api/events").mock(
            return_value=Response(200, json={"id": "e4"})
        )
        cli.cmd_log("hello from cli")
        body = json.loads(route.calls[0].request.content)
        assert body["payload"]["message"] == "hello from cli"


class TestCmdNew:
    @respx.mock
    def test_creates_ticket_and_prints_criteria(self, configured, capsys):
        respx.post(f"{BASE}/api/tickets").mock(return_value=Response(200, json={
            "id": "tk-1", "title": "New thing",
            "acceptance_criteria": [{"id": "c1" * 8, "text": "crit one", "done": False}],
        }))
        with patch("builtins.input", side_effect=["a description", "n"]):
            cli.cmd_new("New thing")
        out = capsys.readouterr().out
        assert "Created ticket tk-1" in out
        assert "crit one" in out
        assert cli.load_session() == {}

    def test_empty_title_exits(self, configured):
        with patch("builtins.input", return_value=""), pytest.raises(SystemExit):
            cli.cmd_new("")


class TestPickTicket:
    def _tickets(self):
        return [
            {"id": "t-open", "title": "Open one", "status": "open",
             "source_id": None, "acceptance_criteria": []},
            {"id": "t-done", "title": "Done one", "status": "done",
             "source_id": None, "acceptance_criteria": []},
        ]

    @respx.mock
    def test_done_tickets_excluded_from_picker(self, configured):
        respx.get(f"{BASE}/api/tickets").mock(
            return_value=Response(200, json=self._tickets())
        )
        with patch("builtins.input", return_value="1"):
            picked = cli._pick_ticket(cli.require_config())
        assert picked == "t-open"

    @respx.mock
    def test_out_of_range_selection_exits(self, configured):
        respx.get(f"{BASE}/api/tickets").mock(
            return_value=Response(200, json=self._tickets())
        )
        with patch("builtins.input", return_value="9"), pytest.raises(SystemExit):
            cli._pick_ticket(cli.require_config())

    @respx.mock
    def test_non_numeric_selection_exits(self, configured):
        respx.get(f"{BASE}/api/tickets").mock(
            return_value=Response(200, json=self._tickets())
        )
        with patch("builtins.input", return_value="abc"), pytest.raises(SystemExit):
            cli._pick_ticket(cli.require_config())


class TestStatus:
    def test_status_without_session(self, capsys):
        cli.cmd_status()
        assert "No active session" in capsys.readouterr().out

    def test_status_with_session_shows_tokens(self, capsys):
        cli.save_session({"ticket_id": "t1", "tokens_in": 1234, "tokens_out": 56})
        cli.cmd_status()
        out = capsys.readouterr().out
        assert "t1" in out
        assert "1,234" in out


class TestInjectHelpers:
    def test_detect_agent_claude_code(self):
        assert cli.detect_agent({"CLAUDE_CODE": "1"}) == "claude-code"

    def test_detect_agent_cursor(self):
        assert cli.detect_agent({"CURSOR_TRACE_ID": "x"}) == "cursor"

    def test_detect_agent_terminal_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cli.detect_agent({}) == "terminal"

    def test_criteria_block_embeds_ids_as_comments(self):
        block = cli._build_criteria_block([
            {"id": "abc", "text": "do it", "done": False},
            {"id": "def", "text": "done it", "done": True},
        ])
        assert "- [ ] do it  <!-- id: abc -->" in block
        assert "- [x] done it  <!-- id: def -->" in block

    def test_replace_or_append_appends_when_absent(self):
        result = cli._replace_or_append("# Existing\n", "## Active Treco Ticket",
                                        "## Active Treco Ticket\nnew\n")
        assert result.count("## Active Treco Ticket") == 1
        assert "# Existing" in result

    def test_replace_or_append_is_idempotent(self):
        section_v1 = "## Active Treco Ticket\nfirst version\n"
        section_v2 = "## Active Treco Ticket\nsecond version\n"
        doc = cli._replace_or_append("# Doc\n", "## Active Treco Ticket", section_v1)
        doc = cli._replace_or_append(doc, "## Active Treco Ticket", section_v2)
        assert doc.count("## Active Treco Ticket") == 1
        assert "second version" in doc
        assert "first version" not in doc


class TestInstallHooks:
    def test_installs_both_hooks_idempotently(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli.Path, "home", classmethod(lambda cls: tmp_path))
        cli._install_hooks()
        cli._install_hooks()

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        post_hooks = settings["hooks"]["PostToolUse"][0]["hooks"]
        assert post_hooks.count({"type": "command", "command": "treco hook post-tool-use"}) == 1
        stop_matchers = [
            h for h in settings["hooks"]["Stop"]
            if {"type": "command", "command": "treco hook stop"} in h.get("hooks", [])
        ]
        assert len(stop_matchers) == 1

    def test_preserves_existing_settings(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli.Path, "home", classmethod(lambda cls: tmp_path))
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({"model": "opus"}))
        cli._install_hooks()
        settings = json.loads((claude_dir / "settings.json").read_text())
        assert settings["model"] == "opus"
        assert "hooks" in settings


class TestMainDispatch:
    def test_unknown_command_exits_1(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["treco", "frobnicate"])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1

    def test_no_args_prints_usage(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["treco"])
        cli.main()
        assert "treco init" in capsys.readouterr().out

    def test_unknown_hook_exits_1(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["treco", "hook", "bogus"])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
