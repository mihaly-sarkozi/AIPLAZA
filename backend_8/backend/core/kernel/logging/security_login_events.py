# backend/core/kernel/logging/security_login_events.py
# Feladat: Login folyamat security eseményeinek logger mixinjét tartalmazza. Sikertelen login okokat és sikeres belépést egységes event névvel, severityvel és request/tenant kontextussal küld tovább. Core auth observability komponens, amelyet a SecurityLogger publikus osztály örököl.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Optional

from core.kernel.logging.security_events import (
    SEV_INFO,
    SEV_WARNING,
    emit_security_log_event,
)

_log_event = emit_security_log_event


class LoginSecurityLoggerMixin:
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


__all__ = ["LoginSecurityLoggerMixin"]
