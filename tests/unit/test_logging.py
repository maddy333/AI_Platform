"""Tests for structured logging configuration."""

import json
import logging

import pytest

from aiplatform.core.config import LoggingSettings
from aiplatform.core.logging import configure_logging, get_logger


def _last_line(captured: str) -> str:
    return captured.strip().splitlines()[-1]


def test_json_format_emits_structured_records(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggingSettings(level="INFO", format="json"))
    get_logger("test.json").info("something_happened", key="value")
    record = json.loads(_last_line(capsys.readouterr().out))
    assert record["event"] == "something_happened"
    assert record["key"] == "value"
    assert record["level"] == "info"
    assert record["logger"] == "test.json"
    assert "timestamp" in record


def test_console_format_renders_event(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggingSettings(level="INFO", format="console"))
    get_logger("test.console").info("console_event")
    assert "console_event" in capsys.readouterr().out


def test_level_filtering_drops_records(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggingSettings(level="WARNING", format="json"))
    get_logger("test.filter").info("should_be_dropped")
    assert capsys.readouterr().out == ""


def test_stdlib_records_flow_through_pipeline(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggingSettings(level="INFO", format="json"))
    logging.getLogger("third.party").info("stdlib message")
    record = json.loads(_last_line(capsys.readouterr().out))
    assert record["event"] == "stdlib message"
    assert record["logger"] == "third.party"
