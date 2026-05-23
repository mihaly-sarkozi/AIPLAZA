# backend/core/kernel/logging/security_logger.py
# Feladat: Strukturált security logger publikus osztályát adja login, logout és refresh mixinekkel. A konkrét eseménycsoportok külön fájlokban élnek, ez az osztály pedig stabil API-t biztosít auth use case-ek és event handlerek számára. Core security observability komponens SIEM/Grafana/ELK jellegű feldolgozáshoz.
# Sárközi Mihály - 2026.05.21

from typing import Any, Optional

from core.kernel.logging.security_events import (
    SEV_INFO,
    emit_security_log_event,
)
from core.kernel.logging.security_login_events import LoginSecurityLoggerMixin
from core.kernel.logging.security_logout_events import LogoutSecurityLoggerMixin
from core.kernel.logging.security_refresh_events import RefreshSecurityLoggerMixin

_log_event = emit_security_log_event


class SecurityLogger(
    LoginSecurityLoggerMixin,
    LogoutSecurityLoggerMixin,
    RefreshSecurityLoggerMixin,
):
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
