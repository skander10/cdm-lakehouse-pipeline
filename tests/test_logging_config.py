"""Tests for the logging setup."""

import logging
from pathlib import Path

from src.logging_config import setup_logging


def read_log(log_file: Path) -> str:
    """Make sure everything is written to disk, then return the log file content."""
    for handler in logging.getLogger().handlers:
        handler.flush()
    return log_file.read_text(encoding="utf-8")


def test_message_is_written_to_log_file(tmp_path: Path) -> None:
    log_file = setup_logging(tmp_path)
    logging.getLogger("src.example").warning("example warning")

    assert "WARNING | src.example | example warning" in read_log(log_file)


def test_log_file_is_overwritten_on_each_run(tmp_path: Path) -> None:
    setup_logging(tmp_path)
    logging.getLogger("src.example").info("first run")
    log_file = setup_logging(tmp_path)
    logging.getLogger("src.example").info("second run")

    content = read_log(log_file)
    assert "first run" not in content
    assert content.count("second run") == 1
