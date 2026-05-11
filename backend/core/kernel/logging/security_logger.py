# Strukturált biztonsági események – SIEM / Grafana / ELK bekötéshez.
# Minden esemény: event_id, severity, tenant_slug, user_id, ip, ua, correlation_id, timestamp (+ opcionális extra).
# Dedikált "security" logger: konfigban külön fájl/szint/formátum, könnyű szűrés.
# 2026.03.07 - Sárközi Mihály

import json
import logging
from typing import Any, Optional

from core.kernel.clock import utc_now
from core.kernel.logging.observability import get_observability_context
from shared.utils import sanitize_log_data

_log = logging.getLogger("security")

# Severity a standard szinteknek megfelelően (SIEM/ELK szűréshez)
SEV_INFO = "INFO"
SEV_WARNING = "WARNING"
SEV_ERROR = "ERROR"


# Ez a függvény a(z) iso_ts logikáját valósítja meg.
def _iso_ts() -> str:
    return utc_now().isoformat()


def _level_for_payload(severity: str) -> str:
    normalized = str(severity or "").upper()
    if normalized == SEV_ERROR:
        return "error"
    if normalized == SEV_WARNING:
        return "warn"
    return "info"


def _sanitize_security_event(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_log_data(payload) or {}
    # A monitoring use-case miatt ezeknél a mezőknél nyers értéket tartunk meg.
    for key in ("email", "ip", "userAgent", "requestId", "userId", "service", "event", "message", "country", "deviceId", "riskScore", "reason"):
        if key in payload and payload.get(key) is not None:
            sanitized[key] = payload.get(key)
    return sanitized


def _log_event(
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
        "timestamp": _iso_ts(),
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
    event = _sanitize_security_event(event)
    msg = json.dumps(event, ensure_ascii=False)
    if severity == SEV_ERROR:
        _log.error("%s", msg)
    elif severity == SEV_WARNING:
        _log.warning("%s", msg)
    else:
        _log.info("%s", msg)


class SecurityLogger:
    """
    Biztonsági események strukturált logolása.
    Minden metódus opcionálisan fogadja a tenant_slug és correlation_id (request id) paramétereket;
    a router/middleware állítja be, így SIEM/Grafana/ELK könnyen szűrhet kérésre.
    """

    def emit_security_event(
        self,
        *,
        event: str,
        level: str = SEV_INFO,
        service: str = "auth",
        message: str,
        tenant_slug: Optional[str] = None,
        user_id: Optional[int] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        _log_event(
            event,
            level,
            service=service,
            message=message,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
            **extra,
        )

    # --- LOGIN (érvénytelen / gyanús = WARNING, sikeres = INFO) ---
    def login_invalid_user_attempt(
        self,
        email: str,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "login_failed",
            SEV_WARNING,
            message="Failed login attempt",
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
            email=email,
            reason="invalid_user",
        )

    # Ez a metódus a(z) login_inactive_user_attempt logikáját valósítja meg.
    def login_inactive_user_attempt(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "login_failed",
            SEV_WARNING,
            message="Failed login attempt",
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
            reason="inactive_user",
        )

    # Ez a metódus a(z) login_bad_password_attempt logikáját valósítja meg.
    def login_bad_password_attempt(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "login_failed",
            SEV_WARNING,
            message="Failed login attempt",
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
            reason="bad_password",
        )

    # Ez a metódus a(z) login_successful_login logikáját valósítja meg.
    def login_successful_login(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "login_success",
            SEV_INFO,
            message="Successful login",
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # --- LOGOUT ---
    def logout_expired_token(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "expired_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) logout_invalid_token logikáját valósítja meg.
    def logout_invalid_token(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "invalid_token",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) logout_wrong_type logikáját valósítja meg.
    def logout_wrong_type(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "invalid_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) logout_unknown_jti logikáját valósítja meg.
    def logout_unknown_jti(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "invalid_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) logout_replay_detected logikáját valósítja meg.
    def logout_replay_detected(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "suspicious_request",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) logout_success logikáját valósítja meg.
    def logout_success(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "logout",
            SEV_INFO,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # --- REFRESH ---
    def refresh_expired_token(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "expired_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) refresh_invalid_token logikáját valósítja meg.
    def refresh_invalid_token(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "invalid_token",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) refresh_wrong_type logikáját valósítja meg.
    def refresh_wrong_type(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "invalid_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) refresh_unknown_jti logikáját valósítja meg.
    def refresh_unknown_jti(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "invalid_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) refresh_reuse_detected logikáját valósítja meg.
    def refresh_reuse_detected(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "suspicious_request",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) refresh_session_expired logikáját valósítja meg.
    def refresh_session_expired(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "expired_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    # Ez a metódus a(z) refresh_success logikáját valósítja meg.
    def refresh_success(
        self,
        user_id: int,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "refresh_success",
            SEV_INFO,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )
