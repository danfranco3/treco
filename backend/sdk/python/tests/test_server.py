"""Tests for server daemon: start/stop/status, PID file lifecycle."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestServerIsRunning:
    def test_not_running_when_no_pid_file(self, tmp_path):
        import treco.server as srv

        with patch.object(srv, "PID_FILE", tmp_path / "server.pid"):
            assert not srv.is_running()

    def test_not_running_when_pid_file_has_dead_pid(self, tmp_path):
        import treco.server as srv

        pid_file = tmp_path / "server.pid"
        pid_file.write_text("999999999")  # very unlikely to be alive
        with patch.object(srv, "PID_FILE", pid_file):
            assert not srv.is_running()

    def test_running_when_pid_alive(self, tmp_path):
        import treco.server as srv

        pid_file = tmp_path / "server.pid"
        pid_file.write_text(str(os.getpid()))  # our own PID is definitely alive
        with patch.object(srv, "PID_FILE", pid_file):
            assert srv.is_running()


class TestServerStop:
    def test_stop_removes_pid_file(self, tmp_path):
        import treco.server as srv

        pid_file = tmp_path / "server.pid"
        pid_file.write_text(str(os.getpid()))

        with (
            patch.object(srv, "PID_FILE", pid_file),
            patch("os.kill"),
        ):
            srv.stop()

        assert not pid_file.exists()

    def test_stop_when_not_running(self, tmp_path, capsys):
        import treco.server as srv

        with patch.object(srv, "PID_FILE", tmp_path / "server.pid"):
            srv.stop()

        captured = capsys.readouterr()
        assert "not running" in captured.out.lower()


class TestBackendDir:
    def test_env_var_override(self, tmp_path):
        import treco.server as srv

        fake_backend = tmp_path / "backend"
        app_dir = fake_backend / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "main.py").write_text("")

        with patch.dict("os.environ", {"TRECO_BACKEND_DIR": str(fake_backend)}):
            result = srv._backend_dir()

        assert result == fake_backend

    def test_env_var_takes_precedence_over_relative_discovery(self, tmp_path):
        import treco.server as srv

        fake_backend = tmp_path / "custom_backend"
        (fake_backend / "app").mkdir(parents=True)
        (fake_backend / "app" / "main.py").write_text("")

        with patch.dict("os.environ", {"TRECO_BACKEND_DIR": str(fake_backend)}):
            result = srv._backend_dir()

        assert result == fake_backend
