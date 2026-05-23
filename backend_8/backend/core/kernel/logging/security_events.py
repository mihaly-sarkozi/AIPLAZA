# backend/core/kernel/logging/security_events.py
# Feladat: Security események közös kibocsátási függvényét és severity konstansait tartalmazza. Az observability contextből automatikusan kiegészíti a request, tenant, user és instance role mezőket, majd sanitizált JSON eseményt ír a dedikált security loggerre. Core security logging helper, amelyet a security logger mixinek használnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from core.kernel.runtime.clock import utc_now
from core.kernel.logging.observability import get_observability_context
from core.kernel.logging.security_payload import sanitize_security_event

SEV_INFO = "INFO"
SEV_WARNING = "WARNING"
SEV_ERROR = "ERROR"

_log = logging.getLogger("security")


def emit_security_log_event(
    event_id: str,
    severity: str,
    *,
    service: str = "auth",
    message: str | None = None,
    tenant_slug: Optional[str] = None,
    user_id: Optional[int] = None,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **extra: Any,
) -> None:
    """Egy soros JSON esemény a security loggerre; üres mezők kihagyva."""
    context = get_observability_context()
    event: dict[str, Any] = {
        "timestamp": utc_now().isoformat(),
        "level": _level_for_payload(severity),
        "event": event_id,
        "service": service,
        "requestId": context.get("request_id"),
        "userId": user_id if user_id is not None else context.get("user_id"),
        "ip": ip,
        "userAgent": ua,
        "message": message or event_id.replace("_", " ").capitalize(),
        # Backward compatibility fields
        "event_name": event_id,
        "severity": severity,
        "request_id": context.get("request_id"),
        "user_id": user_id if user_id is not None else context.get("user_id"),
        "ua": ua,
        "tenant_id": context.get("tenant_id"),
        "tenant_slug": tenant_slug if tenant_slug is not None else context.get("tenant_slug"),
        "correlation_id": correlation_id if correlation_id is not None else context.get("correlation_id"),
        "instance_role": context.get("instance_role"),
    }
    for key, value in extra.items():
        if value is not None:
            event[key] = value
    msg = json.dumps(sanitize_security_event(event), ensure_ascii=False)
    if severity == SEV_ERROR:
        _log.error("%s", msg)
    elif severity == SEV_WARNING:
        _log.warning("%s", msg)
    else:
        _log.info("%s", msg)


def _level_for_payload(severity: str) -> str:
    normalized = str(severity or "").upper()
    if normalized == SEV_ERROR:
        return "error"
    if normalized == SEV_WARNING:
        return "warn"
    return "info"


__all__ = [
    "SEV_ERROR",
    "SEV_INFO",
    "SEV_WARNING",
    "emit_security_log_event",
]
