"""Structured logging configuration for queryable application events."""

from __future__ import annotations

import datetime
import json
import logging
import sys
import traceback
from typing import Any

from app.config.settings import settings
from app.utils.wide_event import wide_event

MAX_LOG_BYTES = 64 * 1024
ESSENTIAL_LOG_FIELDS = {
    "timestamp",
    "level",
    "logger",
    "message",
    "event",
    "request_id",
    "scan.session_id",
    "persistence.status",
    "http.status",
    "http.duration_ms",
    "http.method",
    "http.path",
    "outcome",
    "error.kind",
    "error.code",
}


class JsonFormatter(logging.Formatter):
    """Render a log record and its ``extra`` fields as one JSON object."""

    _reserved = set(vars(logging.makeLogRecord({}))) | {
        "asctime",
        "message",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = wide_event.request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        payload.update(self._error_fields(record))
        payload.update(self._extra_fields(record))
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        encoded_bytes = len(encoded.encode("utf-8"))
        if encoded_bytes <= MAX_LOG_BYTES:
            return encoded
        # A valid, bounded JSON summary is preferable to a cut-off log line.
        summary = {
            key: value[:512] if isinstance(value, str) else value
            for key, value in payload.items()
            if key in ESSENTIAL_LOG_FIELDS
            and isinstance(value, (str, int, float, bool, type(None)))
        }
        summary.update({"log.truncated": True, "log.original_bytes": encoded_bytes})
        return json.dumps(summary, ensure_ascii=False, default=str)

    def _extra_fields(self, record: logging.LogRecord) -> dict[str, Any]:
        return {
            key: self._jsonable(value)
            for key, value in record.__dict__.items()
            if key not in self._reserved and not key.startswith("_")
        }

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [cls._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._jsonable(item) for key, item in value.items()}
        return str(value)

    @staticmethod
    def _error_fields(record: logging.LogRecord) -> dict[str, str]:
        if record.exc_info is None:
            return {}
        error_type, error, traceback_value = record.exc_info
        return {
            "error.kind": getattr(error_type, "__name__", str(error_type)),
            "error.message": str(error),
            "error.stack": "".join(
                traceback.format_exception(error_type, error, traceback_value)
            ),
        }


class LoggingConfigurator:
    """Install the application JSON formatter on the root logger."""

    def configure(self) -> None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(
            level=settings.LOG_LEVEL,
            handlers=[handler],
            force=True,
        )
        self._silence_duplicate_access_logs()
        logging.getLogger(__name__).info(
            "logging configured",
            extra={
                "event": "logging.configured",
                "app.name": settings.APP_NAME,
                "app.version": settings.APP_VERSION,
            },
        )

    @staticmethod
    def _silence_duplicate_access_logs() -> None:
        for logger_name in ("uvicorn.access", "gunicorn.access"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)


def config_logger() -> None:
    """Configure structured application logging."""
    LoggingConfigurator().configure()
