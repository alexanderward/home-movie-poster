"""Correlated, redacted events shared by HTTP, monitors, and commands."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

_context: ContextVar[dict[str, object]] = ContextVar("production_log_context", default={})
_secret = re.compile(
    r"authorization|cookie|password|token|secret|key$|prompt|body|poster.url|cover.url", re.I
)
_logger = logging.getLogger("poster.production")
_service = "api"


def sanitize(value: object, depth: int = 0) -> object:
    if depth > 5:
        return "[depth limit]"
    if isinstance(value, BaseException):
        return {"type": type(value).__name__}
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if _secret.search(str(key)) else sanitize(item, depth + 1)
            for key, item in list(value.items())[:40]
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item, depth + 1) for item in value[:20]]
    if isinstance(value, str):
        if re.search(r"https?://|Bearer\s", value, re.I):
            return "[redacted value]"
        return value[:1000].replace("\r", "\\r").replace("\n", "\\n")
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return "[unsupported value]"


@contextmanager
def log_context(**fields: object) -> Iterator[None]:
    token = _context.set({**_context.get(), **fields})
    try:
        yield
    finally:
        _context.reset(token)


def event(name: str, *, level: int = logging.INFO, **fields: object) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_.]+", name):
        raise ValueError("Log events must use stable domain.action.result names")
    _logger.log(level, name, extra={"fields": sanitize({**_context.get(), **fields})})


def record_fields(record: logging.LogRecord) -> dict[str, object]:
    return {
        "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
        "level": record.levelname,
        "service": _service,
        "event": record.getMessage(),
        **getattr(record, "fields", {}),
    }


class EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = record_fields(record)
        if os.environ.get("LOG_JSON", "false").lower() in {"1", "true", "yes"}:
            return json.dumps(data, ensure_ascii=False)
        return " ".join(f"[{key}:{value}]" for key, value in data.items())


class ConsoleHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stderr
        super().emit(record)


def configure(config: object = None, *, service: str = "api") -> None:
    del config
    global _service
    _service = service
    for handler in _logger.handlers[:]:
        _logger.removeHandler(handler)
        handler.close()
    _logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    _logger.propagate = False
    console = ConsoleHandler()
    console.setFormatter(EventFormatter())
    _logger.addHandler(console)
