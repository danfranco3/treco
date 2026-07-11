"""Tests for cmd_ps: list agents in workspace."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

import treco.cli as cli

CFG = {"api_key": "test-key", "base_url": "http://localhost:8001", "workspace_id": "demo"}

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

SAMPLE_AGENTS = [
    {
        "id": "agent-1",
        "name": "build-bot",
        "status": "working",
        "current_ticket_id": "abc12345-0000-0000-0000-000000000000",
        "workspace_id": "demo",
        "last_seen_at": "2024-01-01T11:58:00",
    },
    {
        "id": "agent-2",
        "name": "review-bot",
        "status": "idle",
        "current_ticket_id": None,
        "workspace_id": "demo",
        "last_seen_at": None,
    },
]


def _mock_client(agents: list, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = agents
    resp.text = ""
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
    mock = MagicMock()
    mock.__enter__ = lambda s: mock
    mock.__exit__ = MagicMock(return_value=False)
    mock.get.return_value = resp
    return mock


class TestCmdPsHappyPath:
    def test_prints_agent_names(self, capsys):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client(SAMPLE_AGENTS)),
        ):
            cli.cmd_ps()
        out = capsys.readouterr().out
        assert "build-bot" in out
        assert "review-bot" in out

    def test_prints_status(self, capsys):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client(SAMPLE_AGENTS)),
        ):
            cli.cmd_ps()
        out = capsys.readouterr().out
        assert "working" in out
        assert "idle" in out

    def test_prints_current_ticket(self, capsys):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client(SAMPLE_AGENTS)),
        ):
            cli.cmd_ps()
        out = capsys.readouterr().out
        assert "abc12345" in out

    def test_dash_for_no_ticket(self, capsys):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client(SAMPLE_AGENTS)),
        ):
            cli.cmd_ps()
        out = capsys.readouterr().out
        assert "-" in out

    def test_never_for_null_last_seen(self, capsys):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client(SAMPLE_AGENTS)),
        ):
            cli.cmd_ps()
        out = capsys.readouterr().out
        assert "never" in out

    def test_empty_workspace_prints_message(self, capsys):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client([])),
        ):
            cli.cmd_ps()
        out = capsys.readouterr().out
        assert "No agents" in out

    def test_passes_workspace_id_as_param(self):
        mock_client = _mock_client(SAMPLE_AGENTS)
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=mock_client),
        ):
            cli.cmd_ps()
        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["workspace_id"] == "demo"

    def test_sends_agent_key_header(self):
        mock_client = _mock_client(SAMPLE_AGENTS)
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=mock_client),
        ):
            cli.cmd_ps()
        headers = mock_client.get.call_args.kwargs["headers"]
        assert headers.get("X-Agent-Key") == "test-key"


class TestCmdPsErrors:
    def test_exits_on_http_error(self):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=_mock_client([], 500)),
            pytest.raises(SystemExit) as exc,
        ):
            cli.cmd_ps()
        assert exc.value.code == 1

    def test_exits_on_connection_error(self):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("refused")

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "_workspace_id", return_value="demo"),
            patch("httpx.Client", return_value=mock_client),
            pytest.raises(SystemExit) as exc,
        ):
            cli.cmd_ps()
        assert exc.value.code == 1


class TestRelativeTime:
    def test_seconds(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        assert cli._relative_time(ts).endswith("s ago")

    def test_minutes(self):
        ts = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        assert cli._relative_time(ts) == "5m ago"

    def test_hours(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        assert cli._relative_time(ts) == "3h ago"

    def test_days(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        assert cli._relative_time(ts) == "2d ago"

    def test_none_returns_never(self):
        assert cli._relative_time(None) == "never"

    def test_invalid_returns_raw(self):
        assert cli._relative_time("not-a-date") == "not-a-date"
