"""Structured JSON logging with conservative field handling."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

_RESERVED = set(logging.makeLogRecord({}).__dict__)
_SENSITIVE = {"password", "secret", "token", "authorization", "credential"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key.lower() not in _SENSITIVE:
                fields[key] = value
        return json.dumps(fields, default=str, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
