"""Tests for logging_config: configure_logging sets up expected handlers."""
import logging

import pytest

from app.core.logging_config import _JSONFormatter, configure_logging


class TestJsonFormatter:
    def test_formats_record_as_json(self):
        import json
        formatter = _JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert "time" in parsed

    def test_formats_record_has_required_keys(self):
        import json
        formatter = _JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="warn", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "WARNING"
        assert parsed["message"] == "warn"
        assert "time" in parsed


class TestConfigureLogging:
    def test_configure_logging_runs_without_error(self):
        configure_logging()  # should not raise

    def test_root_logger_has_handler_after_configure(self):
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) >= 1

    def test_uvicorn_access_logger_does_not_propagate(self):
        configure_logging()
        logger = logging.getLogger("uvicorn.access")
        assert logger.propagate is False
