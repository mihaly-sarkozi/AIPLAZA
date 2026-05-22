# backend/core/kernel/security/errors.py
# Feladat: Security konfigurációs hibák közös exception típusát definiálja. A startup guardok ezt dobják, amikor olyan beállítást találnak, amellyel az alkalmazás nem indulhat biztonságosan. Core security error contract a startup ellenőrzésekhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import HTTPException

from core.kernel.http.error_payloads import build_security_error_detail


class SecurityConfigError(ValueError):
    """Akkor dob, ha indítási biztonsági validáció meghiúsul."""


def security_http_exception(
    *,
    status_code: int = 403,
    code: str = "PERMISSION_DENIED",
    message: str = "You are not allowed to access this resource.",
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=build_security_error_detail(code=code, message=message),
    )


__all__ = ["SecurityConfigError", "security_http_exception"]
