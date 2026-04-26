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
    context = get_observability_context()
    event: dict[str, Any] = {
        "event_name": event_id,
        "severity": severity,
        "timestamp": _iso_ts(),
        "request_id": context.get("request_id"),
        "tenant_id": context.get("tenant_id"),
        "tenant_slug": tenant_slug if tenant_slug is not None else context.get("tenant_slug"),
        "user_id": user_id if user_id is not None else context.get("user_id"),
        "correlation_id": correlation_id if correlation_id is not None else context.get("correlation_id"),
        "instance_role": context.get("instance_role"),
    }
    if ip is not None:
        event["ip"] = ip
    if ua is not None:
        event["ua"] = ua
    event.update(extra)
    event = sanitize_log_data(event) or {}
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
            "login_inactive_user_attempt",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
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
            "login_bad_password_attempt",
            SEV_WARNING,
            tenant_slug=tenant_slug,
            user_id=user_id,
            ip=ip,
            ua=ua,
            correlation_id=correlation_id,
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
            "logout_invalid_token",
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
            "logout_wrong_type",
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
            "logout_unknown_jti",
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
            "logout_replay_detected",
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
            "refresh_invalid_token",
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
            "refresh_wrong_type",
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
            "refresh_unknown_jti",
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
            "refresh_reuse_detected",
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
            "refresh_session_expired",
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
