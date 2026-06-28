"""Logging estruturado em JSON-lines.

Cada evento é uma linha; PII é redigida antes de escrever; `trace_id`
correlaciona os eventos de um turno.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from ..security.redaction import redact_obj

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    def __init__(self, redact_pii: bool) -> None:
        super().__init__()
        self._redact = redact_pii

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if self._redact:
            payload = redact_obj(payload)  # type: ignore[assignment]
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    level: str = "INFO", redact_pii: bool = True, log_file: str | None = None
) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler: logging.Handler = (
        logging.FileHandler(log_file, encoding="utf-8")
        if log_file
        else logging.StreamHandler(sys.stdout)
    )
    handler.setFormatter(_JsonFormatter(redact_pii))
    root = logging.getLogger("bia")
    root.setLevel(level)
    root.handlers = [handler]
    root.propagate = False
    _CONFIGURED = True


class TraceLogger:
    """Logger que injeta `trace_id` e campos estruturados em cada evento."""

    def __init__(self, trace_id: str) -> None:
        self._trace_id = trace_id
        self._log = logging.getLogger("bia")

    def event(self, name: str, level: int = logging.INFO, **fields: Any) -> None:
        fields["trace_id"] = self._trace_id
        self._log.log(level, name, extra={"extra_fields": fields})

    def info(self, name: str, **fields: Any) -> None:
        self.event(name, logging.INFO, **fields)

    def warning(self, name: str, **fields: Any) -> None:
        self.event(name, logging.WARNING, **fields)

    def error(self, name: str, **fields: Any) -> None:
        self.event(name, logging.ERROR, **fields)
