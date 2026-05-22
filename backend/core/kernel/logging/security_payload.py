# backend/core/kernel/logging/security_payload.py
# Feladat: Security log payloadok sanitizálását központosítja. Az általános log sanitizer után néhány monitoring szempontból fontos nyers mezőt visszaenged, például emailt, ip-t, requestId-t és riskScore-t. Belső core security logging helper, amely az auditálhatóság és adatvédelem közti egyensúlyt kezeli.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from shared.utils import sanitize_log_data

RAW_SECURITY_EVENT_FIELDS = (
    "email",
    "ip",
    "userAgent",
    "requestId",
    "userId",
    "service",
    "event",
    "message",
    "country",
    "deviceId",
    "riskScore",
    "reason",
)


def sanitize_security_event(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_log_data(payload) or {}
    # A monitoring use-case miatt ezeknél a mezőknél nyers értéket tartunk meg.
    for key in RAW_SECURITY_EVENT_FIELDS:
        if key in payload and payload.get(key) is not None:
            sanitized[key] = payload.get(key)
    return sanitized


__all__ = ["sanitize_security_event"]
