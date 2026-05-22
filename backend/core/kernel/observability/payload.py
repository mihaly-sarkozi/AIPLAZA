# backend/core/kernel/observability/payload.py
# Feladat: Strukturált log payloadok alap kontextusát, JSON-biztosítását és sanitizálását végzi. Az observability context mellé instance role-t ad, majd eldönti, mely mezők tarthatók meg nyersen és melyeket kell a közös sanitizerre bízni. Core logging payload helper adatvédelmi és megfigyelhetőségi célokra.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json
from typing import Any

from core.kernel.runtime.instance_role import get_instance_role
from core.kernel.observability.context import get_observability_context
from shared.utils import sanitize_log_data

_SAFE_FIELD_NAMES = frozenset(
    {
        "actor_type",
        "auth_outcome",
        "batch_id",
        "claimed_count",
        "component",
        "correlation_id",
        "channel_id",
        "db_query_count",
        "db_query_total_ms",
        "elapsed_ms",
        "error_type",
        "error_message",
        "event_id",
        "event_name",
        "event",
        "service",
        "requestId",
        "userId",
        "userAgent",
        "deviceId",
        "riskScore",
        "event_type",
        "country",
        "reason",
        "idempotency_key",
        "ingest_item_id",
        "ingest_run_id",
        "instance_role",
        "job_id",
        "knowledge_base_id",
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
        "session_id",
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

def default_log_context() -> dict[str, Any]:
    context = get_observability_context()
    if "instance_role" not in context:
        try:
            context["instance_role"] = get_instance_role().value
        except Exception:
            context["instance_role"] = None
    return context


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, BaseException):
            return str(value)
        return repr(value)


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SAFE_FIELD_NAMES or key.endswith(("_id", "_ms", "_count")):
            if isinstance(value, dict):
                sanitized[key] = {nested_key: json_safe(nested_value) for nested_key, nested_value in value.items()}
            else:
                sanitized[key] = value
            continue
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value) or {}
            continue
        maybe_sanitized = sanitize_log_data({key: value}) or {}
        sanitized[key] = maybe_sanitized.get(key)
    return sanitized


__all__ = ["default_log_context", "json_safe", "sanitize_payload"]
