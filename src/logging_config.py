"""Logging setup, called once when the pipeline starts.

Every log message goes to the console and to logs/pipeline.log.
Each module gets its own logger with:  logger = logging.getLogger(__name__)
"""

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(logs_dir: Path) -> Path:
    """Send log messages to the console and to logs/pipeline.log (overwritten on every run)."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "pipeline.log"
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(),  # console
            logging.FileHandler(log_file, mode="w", encoding="utf-8"),  # file, overwritten
        ],
        force=True,  # replace any earlier setup, so no line is written twice
    )
    return log_file