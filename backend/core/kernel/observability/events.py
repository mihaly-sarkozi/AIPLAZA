# backend/core/kernel/observability/events.py
# Feladat: Strukturált event és exception logolást biztosít JSON log pipeline felé. Alap observability kontextust és timestampet ad az eseményekhez, JSON-biztossá és sanitizálttá teszi a mezőket, majd a megadott loggerre ír. Core observability emitter, amelyet HTTP, DB, events és app modulok is használhatnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

from core.kernel.runtime.clock import utc_now
from core.kernel.observability.payload import default_log_context, json_safe, sanitize_payload


def _utc_now_iso() -> str:
    return utc_now().isoformat()


def log_structured_event(
    logger_name: str,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event_name": event,
        "timestamp": _utc_now_iso(),
    }
    payload.update(default_log_context())
    for key, value in fields.items():
        if value is not None:
            payload[key] = json_safe(value)
    payload = sanitize_payload(payload)
    logging.getLogger(logger_name).log(level, "%s", json.dumps(payload, ensure_ascii=False, sort_keys=True))


def log_exception_event(
    logger_name: str,
    event: str,
    error: BaseException,
    *,
    level: int = logging.ERROR,
    include_traceback: bool = True,
    **fields: Any,
) -> None:
    payload = {
        **fields,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if include_traceback:
        payload["traceback"] = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    log_structured_event(logger_name, event, level=level, **payload)


__all__ = ["log_exception_event", "log_structured_event"]
