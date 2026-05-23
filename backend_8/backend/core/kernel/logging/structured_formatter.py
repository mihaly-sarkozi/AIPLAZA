# backend/core/kernel/logging/structured_formatter.py
# Feladat: Python LogRecord objektumokból egységes, sanitizált JSON log sort készít. Hozzáadja az alap observability kontextust, kezeli a már JSON-ként érkező üzeneteket és exception mezőket is. Core logging formatter Grafana/Loki vagy hasonló loggyűjtő irányába.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json
import logging
from typing import Any

from core.kernel.runtime.clock import utc_now
from core.kernel.observability.payload import default_log_context, sanitize_payload


def _utc_now_iso() -> str:
    return utc_now().isoformat()


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "component": record.name,
        }
        payload.update(default_log_context())

        message = record.getMessage()
        structured_message: dict[str, Any] | None = None
        if message:
            try:
                maybe_json = json.loads(message)
                if isinstance(maybe_json, dict):
                    structured_message = maybe_json
            except Exception:
                structured_message = None

        if structured_message is not None:
            payload.update(structured_message)
        elif message:
            payload["message"] = message

        if record.exc_info:
            exc_type, exc, _ = record.exc_info
            payload["error_type"] = exc_type.__name__ if exc_type else None
            payload["error_message"] = str(exc) if exc else message
            payload["traceback"] = self.formatException(record.exc_info)

        payload = sanitize_payload(payload)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


__all__ = ["StructuredJsonFormatter"]
