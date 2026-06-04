"""Logging configuration helpers."""

from __future__ import annotations

import datetime
import logging
import logging.config
from typing import Any

from settings import get_settings


class RFC3339Formatter(logging.Formatter):
    """Formatter that renders timestamps using local RFC3339 format."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        """Format a log record timestamp as a local RFC3339 string."""
        del datefmt
        dt = datetime.datetime.fromtimestamp(
            record.created,
            datetime.UTC,
        ).astimezone()
        return dt.isoformat(timespec="seconds")


def build_logging_config() -> dict[str, Any]:
    """Build logging configuration from runtime settings."""
    log_level = get_settings().log_level
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
        "formatters": {
            "standard": {
                "()": RFC3339Formatter,
                "format": "[%(asctime)s] %(levelname)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "stream": "ext://sys.stdout",
                "formatter": "standard",
            },
        },
    }


def setup_logging() -> None:
    """Configure application logging."""
    logging.config.dictConfig(build_logging_config())
