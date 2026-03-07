# apps/core/security/security_logger.py
# Strukturált biztonsági események – SIEM / Grafana / ELK bekötéshez.
# Minden esemény: event_id, severity, tenant_slug, user_id, ip, ua, correlation_id, timestamp (+ opcionális extra).
# Dedikált "security" logger: konfigban külön fájl/szint/formátum, könnyű szűrés.
# 2026.03.07 - Sárközi Mihály

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

_log = logging.getLogger("security")

# Severity a standard szinteknek megfelelően (SIEM/ELK szűréshez)
SEV_INFO = "INFO"
SEV_WARNING = "WARNING"
SEV_ERROR = "ERROR"


def _iso_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_event(
    event_id: str,
    severity: str,
    *,
    tenant_slug: Optional[str] = None,
    user_id: Optional[int] = None,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **extra: Any,
) -> None:
    """Egy soros JSON esemény a security loggerre; üres mezők kihagyva."""
    event: dict[str, Any] = {
        "event_id": event_id,
        "severity": severity,
        "timestamp": _iso_ts(),
    }
    if tenant_slug is not None:
        event["tenant_slug"] = tenant_slug
    if user_id is not None:
        event["user_id"] = user_id
    if ip is not None:
        event["ip"] = ip
    if ua is not None:
        event["ua"] = ua
    if correlation_id is not None:
        event["correlation_id"] = correlation_id
    event.update(extra)
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
            "login_invalid_user_attempt",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
            email=email,
        )

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
            "login_inactive_user_attempt",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "login_bad_password_attempt",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "logout_expired_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    def logout_invalid_token(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "logout_invalid_token",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    def logout_wrong_type(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "logout_wrong_type",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "logout_unknown_jti",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "logout_replay_detected",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "logout_success",
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
            "refresh_expired_token",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    def refresh_invalid_token(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "refresh_invalid_token",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

    def refresh_wrong_type(
        self,
        ip: Optional[str],
        ua: Optional[str],
        *,
        tenant_slug: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        _log_event(
            "refresh_wrong_type",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "refresh_unknown_jti",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "refresh_reuse_detected",
            SEV_ERROR,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
            "refresh_session_expired",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
        )

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
