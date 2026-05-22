# backend/core/kernel/logging/security_refresh_events.py
# Feladat: Refresh token folyamat security eseményeinek logger mixinjét tartalmazza. Lejárt, hibás, rossz típusú, ismeretlen vagy reuse gyanús refresh eseményeket és sikeres refresh-t naplóz. Core auth observability komponens, amelyet a SecurityLogger publikus osztály örököl.
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


class RefreshSecurityLoggerMixin:
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


__all__ = ["RefreshSecurityLoggerMixin"]
