from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import threading
import traceback
from contextlib import contextmanager
from typing import Any

from core.kernel.config.instance_role import get_instance_role
from core.kernel.clock import utc_now
from shared.utils import sanitize_log_data

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "observability_context",
    default={},
)


def _utc_now_iso() -> str:
    return utc_now().isoformat()


class InMemoryMetricRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: dict[str, dict[str, Any]] = {}

    def observe(
        self,
        name: str,
        value: float,
        *,
        unit: str = "count",
        tags: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            current = self._stats.get(name)
            if current is None:
                self._stats[name] = {
                    "count": 1,
                    "sum": float(value),
                    "min": float(value),
                    "max": float(value),
                    "last": float(value),
                    "unit": unit,
                    "tags": dict(tags or {}),
                }
                return
            current["count"] += 1
            current["sum"] += float(value)
            current["min"] = min(float(current["min"]), float(value))
            current["max"] = max(float(current["max"]), float(value))
            current["last"] = float(value)
            if tags:
                current["tags"] = dict(tags)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                name: dict(values)
                for name, values in self._stats.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


_metrics = InMemoryMetricRegistry()
_SAFE_FIELD_NAMES = frozenset(
    {
        "actor_type",
        "auth_outcome",
        "batch_id",
        "claimed_count",
        "component",
        "correlation_id",
        "db_query_count",
        "db_query_total_ms",
        "elapsed_ms",
        "error_type",
        "error_message",
        "event_id",
        "event_name",
        "event_type",
        "idempotency_key",
        "instance_role",
        "level",
        "lock_owner",
        "logger",
        "message",
        "method",
        "mode",
        "outcome",
        "path",
        "request_id",
        "response_started",
        "retry_count",
        "stale_lock_after_sec",
        "status_code",
        "tenant_id",
        "tenant_resolution_outcome",
        "tenant_slug",
        "timeout_sec",
        "timestamp",
        "total_ms",
        "traceback",
        "user_id",
        "worker_role",
        "worker_run_id",
    }
)


def get_observability_context() -> dict[str, Any]:
    return dict(_context.get())


def bind_observability_context(**fields: Any):
    current = get_observability_context()
    for key, value in fields.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    return _context.set(current)


def reset_observability_context(token) -> None:
    _context.reset(token)


@contextmanager
def observability_scope(**fields: Any):
    token = bind_observability_context(**fields)
    try:
        yield
    finally:
        reset_observability_context(token)


def set_correlation_id(value: str | None) -> None:
    bind_observability_context(correlation_id=(value or "").strip() or None)


def set_request_id(value: str | None) -> None:
    bind_observability_context(request_id=(value or "").strip() or None)


def set_tenant_context(*, tenant_id: int | None = None, tenant_slug: str | None = None) -> None:
    bind_observability_context(tenant_id=tenant_id, tenant_slug=tenant_slug)


def set_user_id(value: int | None) -> None:
    bind_observability_context(user_id=value)


def get_correlation_id() -> str | None:
    value = get_observability_context().get("correlation_id")
    return str(value) if value else None


def get_request_id() -> str | None:
    value = get_observability_context().get("request_id")
    return str(value) if value else None


def clear_correlation_id() -> None:
    bind_observability_context(correlation_id=None, request_id=None)


def clear_observability_context() -> None:
    _context.set({})


def increment_metric(
    name: str,
    value: float = 1.0,
    *,
    unit: str = "count",
    tags: dict[str, Any] | None = None,
) -> None:
    _metrics.observe(name, value, unit=unit, tags=tags)


def observe_metric(
    name: str,
    value: float,
    *,
    unit: str = "count",
    tags: dict[str, Any] | None = None,
) -> None:
    _metrics.observe(name, value, unit=unit, tags=tags)


def get_metrics_snapshot() -> dict[str, dict[str, Any]]:
    return _metrics.snapshot()


def reset_metrics() -> None:
    _metrics.reset()


def _default_log_context() -> dict[str, Any]:
    context = get_observability_context()
    if "instance_role" not in context:
        try:
            context["instance_role"] = get_instance_role().value
        except Exception:
            context["instance_role"] = None
    return context


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, BaseException):
            return str(value)
        return repr(value)


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SAFE_FIELD_NAMES or key.endswith(("_id", "_ms", "_count")):
            if isinstance(value, dict):
                sanitized[key] = {nested_key: _json_safe(nested_value) for nested_key, nested_value in value.items()}
            else:
                sanitized[key] = value
            continue
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value) or {}
            continue
        maybe_sanitized = sanitize_log_data({key: value}) or {}
        sanitized[key] = maybe_sanitized.get(key)
    return sanitized


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
    payload.update(_default_log_context())
    for key, value in fields.items():
        if value is not None:
            payload[key] = _json_safe(value)
    payload = _sanitize_payload(payload)
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


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "component": record.name,
        }
        payload.update(_default_log_context())

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

        payload = _sanitize_payload(payload)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_structured_logging(*, level: int | None = None) -> None:
    effective_level = level
    if effective_level is None:
        raw = os.environ.get("LOG_LEVEL") or "INFO"
        effective_level = getattr(logging, raw.strip().upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredJsonFormatter())
    logging.basicConfig(level=effective_level, handlers=[handler], force=True)


__all__ = [
    "bind_observability_context",
    "clear_correlation_id",
    "clear_observability_context",
    "configure_structured_logging",
    "get_correlation_id",
    "get_observability_context",
    "get_metrics_snapshot",
    "get_request_id",
    "increment_metric",
    "log_exception_event",
    "log_structured_event",
    "observe_metric",
    "observability_scope",
    "reset_observability_context",
    "reset_metrics",
    "set_correlation_id",
    "set_request_id",
    "set_tenant_context",
    "set_user_id",
]
