# backend/core/kernel/logging/security_logout_events.py
# Feladat: Logout folyamat security eseményeinek logger mixinjét tartalmazza. Lejárt, hibás, rossz típusú vagy replay gyanús token eseményeket és sikeres logoutot strukturált security loggá alakít. Core auth observability komponens, amelyet a SecurityLogger publikus osztály örököl.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Optional

from core.kernel.logging.security_events import (
    SEV_ERROR,
    SEV_INFO,
    SEV_WARNING,
    emit_security_log_event,
)

_log_event = emit_security_log_event


class LogoutSecurityLoggerMixin:
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


__all__ = ["LogoutSecurityLoggerMixin"]
