"""Tests for cmd_logs: event streaming for a ticket."""
import sys
from unittest.mock import MagicMock, patch

import pytest

import treco.cli as cli

SAMPLE_EVENTS = [
    {
        "id": "evt-1",
        "agent_id": "agent-1",
        "ticket_id": "ticket-abc",
        "workspace_id": "demo",
        "event_type": "ticket_started",
        "criterion_id": None,
        "tokens_in": 0,
        "tokens_out": 0,
        "model": None,
        "payload": {},
        "created_at": "2024-01-01T10:00:00",
    },
    {
        "id": "evt-2",
        "agent_id": "agent-1",
        "ticket_id": "ticket-abc",
        "workspace_id": "demo",
        "event_type": "log",
        "criterion_id": None,
        "tokens_in": 100,
        "tokens_out": 50,
        "model": "claude-haiku-4-5-20251001",
        "payload": {"message": "Read file: main.py"},
        "created_at": "2024-01-01T10:01:00",
    },
]

CFG = {"api_key": "test-key", "base_url": "http://localhost:8001"}


def _mock_response(events: list, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = events
    resp.text = "not found" if status_code == 404 else ""
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


class TestCmdLogsHappyPath:
    def test_prints_events(self, capsys):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = _mock_response(SAMPLE_EVENTS)

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={"ticket_id": "ticket-abc"}),
            patch("httpx.Client", return_value=mock_client),
        ):
            cli.cmd_logs("ticket-abc", limit=50, follow=False)

        out = capsys.readouterr().out
        assert "ticket_started" in out
        assert "log" in out
        assert "Read file: main.py" in out

    def test_uses_session_ticket_id_when_not_given(self, capsys):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = _mock_response(SAMPLE_EVENTS)

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={"ticket_id": "ticket-abc"}),
            patch("httpx.Client", return_value=mock_client),
        ):
            cli.cmd_logs("", limit=50, follow=False)

        call_url = mock_client.get.call_args[0][0]
        assert "ticket-abc" in call_url

    def test_limit_truncates_output(self, capsys):
        events = [
            {**SAMPLE_EVENTS[0], "id": f"evt-{i}", "created_at": f"2024-01-01T10:0{i}:00"}
            for i in range(5)
        ]
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = _mock_response(events)

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={}),
            patch("httpx.Client", return_value=mock_client),
        ):
            cli.cmd_logs("ticket-abc", limit=2, follow=False)

        out = capsys.readouterr().out
        assert out.count("ticket_started") == 2

    def test_token_counts_shown_in_output(self, capsys):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = _mock_response(SAMPLE_EVENTS)

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={}),
            patch("httpx.Client", return_value=mock_client),
        ):
            cli.cmd_logs("ticket-abc", follow=False)

        out = capsys.readouterr().out
        assert "100↑" in out
        assert "50↓" in out


class TestCmdLogsErrors:
    def test_exits_when_no_ticket_and_no_session(self):
        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={}),
            pytest.raises(SystemExit) as exc,
        ):
            cli.cmd_logs("", follow=False)
        assert exc.value.code == 1

    def test_exits_on_404(self):
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"
        mock_client.get.return_value = mock_resp

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={}),
            patch("httpx.Client", return_value=mock_client),
            pytest.raises(SystemExit) as exc,
        ):
            cli.cmd_logs("no-such-ticket", follow=False)
        assert exc.value.code == 1

    def test_exits_on_http_error(self):
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=mock_resp
        )
        mock_client.get.return_value = mock_resp

        with (
            patch.object(cli, "require_config", return_value=CFG),
            patch.object(cli, "load_session", return_value={}),
            patch("httpx.Client", return_value=mock_client),
            pytest.raises(SystemExit) as exc,
        ):
            cli.cmd_logs("ticket-abc", follow=False)
        assert exc.value.code == 1


class TestFormatEvent:
    def test_formats_timestamp_and_type(self):
        ev = {**SAMPLE_EVENTS[0]}
        line = cli._format_event(ev)
        assert "2024-01-01 10:00:00" in line
        assert "ticket_started" in line

    def test_shows_message_from_payload(self):
        ev = {**SAMPLE_EVENTS[1]}
        line = cli._format_event(ev)
        assert "Read file: main.py" in line

    def test_no_token_display_when_zero(self):
        ev = {**SAMPLE_EVENTS[0]}
        line = cli._format_event(ev)
        assert "↑" not in line
        assert "↓" not in line
