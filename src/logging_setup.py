"""Logging configuration helpers for the listing monitor application."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | int = DEFAULT_LOG_LEVEL) -> None:
    """Configure process-wide logging for local runs and scheduled execution."""

    logging.basicConfig(
        level=_normalize_log_level(level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for application modules."""

    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a simple structured log line with an explicit event name."""

    message_parts = [f"event={event}"]
    for field_name, value in fields.items():
        message_parts.append(f"{field_name}={_serialize_log_value(value)}")

    logger.log(level, " ".join(message_parts))


def _normalize_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level

    normalized_level = level.strip().upper()
    if not normalized_level:
        return logging.INFO

    resolved_level = logging.getLevelName(normalized_level)
    if isinstance(resolved_level, int):
        return resolved_level

    return logging.INFO


def _serialize_log_value(value: Any) -> str:
    if isinstance(value, Path):
        return json.dumps(str(value))

    if value is None:
        return "null"

    if isinstance(value, bool):
        return str(value).lower()

    if isinstance(value, int | float):
        return str(value)

    return json.dumps(str(value))
