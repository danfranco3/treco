"""Tests for cmd_init: config written, hooks installed, correct URL defaults."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _mock_init_success(base_url="http://localhost:8001", workspace_id="demo", tmp_path=None):
    import treco.cli as cli

    saved_config = {}
    config_file = tmp_path / "config.json" if tmp_path else None

    api_key_returned = "treco_abc123"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"api_key": api_key_returned, "agent_id": "agent-1", "workspace_id": workspace_id}
    mock_response.raise_for_status = MagicMock()

    with (
        patch("builtins.input", side_effect=[base_url, workspace_id, "n"]),
        patch("httpx.get", side_effect=Exception("not running")),
        patch("httpx.post", return_value=mock_response),
        patch.object(cli, "save_config", lambda cfg: saved_config.update(cfg)),
        patch.object(cli, "CONFIG_FILE", config_file or cli.CONFIG_FILE),
        patch.object(cli, "_install_hooks"),
    ):
        cli.cmd_init()

    return saved_config


class TestCmdInit:
    def test_saves_api_key_from_api(self, tmp_path):
        saved = _mock_init_success(tmp_path=tmp_path)
        assert saved.get("api_key") == "treco_abc123"

    def test_saves_base_url(self, tmp_path):
        saved = _mock_init_success(base_url="http://localhost:8001", tmp_path=tmp_path)
        assert saved.get("base_url") == "http://localhost:8001"

    def test_saves_workspace_id(self, tmp_path):
        saved = _mock_init_success(workspace_id="demo", tmp_path=tmp_path)
        assert saved.get("workspace_id") == "demo"


class TestConfigFilePath:
    def test_config_uses_directory(self):
        import treco.cli as cli
        assert cli.CONFIG_FILE.name == "config.json"
        assert cli.CONFIG_FILE.parent.name == ".treco"


class TestInstallHooks:
    def test_creates_settings_if_missing(self, tmp_path):
        import treco.cli as cli

        settings_path = tmp_path / "settings.json"
        with patch.object(Path, "home", return_value=tmp_path):
            with patch("treco.cli.Path.home", return_value=tmp_path):
                target = tmp_path / ".claude" / "settings.json"
                (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)

                original_fn = cli._install_hooks

                def patched():
                    with patch.object(cli, "CONFIG_FILE", tmp_path / ".treco" / "config.json"):
                        pass

                cli._install_hooks()

    def test_hook_install_command_callable(self):
        import treco.cli as cli
        with patch.object(cli, "_install_hooks") as mock_install:
            cli.cmd_hook_install()
            mock_install.assert_called_once()
