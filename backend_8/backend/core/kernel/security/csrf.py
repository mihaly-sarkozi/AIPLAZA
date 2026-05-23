# backend/core/kernel/security/csrf.py
# Feladat: Double-submit CSRF token generálást, cookie beállítást és request validációs helperöket ad. A token cookie és az X-CSRF-Token header egyezését ellenőrzi, külön platform-admin cookie scope-pal. Core HTTP security helper, amelyet auth/admin routerek és a CSRF middleware használnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_PATH = "/api"
PLATFORM_ADMIN_CSRF_COOKIE_NAME = "platform_admin_csrf_token"
PLATFORM_ADMIN_CSRF_COOKIE_PATH = "/api/platform-admin"


# Ez a függvény a(z) generate_csrf_token logikáját valósítja meg.
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: "Response",
    value: str,
    *,
    secure: bool,
    samesite: str = "lax",
) -> None:
    """Set CSRF token cookie (SameSite strict recommended for CSRF)."""
    response.set_cookie(
        CSRF_COOKIE_NAME,
        value,
        path=CSRF_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
    )


def set_platform_admin_csrf_cookie(
    response: "Response",
    value: str,
    *,
    secure: bool,
    samesite: str = "lax",
) -> None:
    """Set CSRF token cookie for platform-admin scope only."""
    response.set_cookie(
        PLATFORM_ADMIN_CSRF_COOKIE_NAME,
        value,
        path=PLATFORM_ADMIN_CSRF_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
    )


def get_csrf_from_request(request: "Request") -> tuple[str | None, str | None]:
    """Return (cookie_value, header_value)."""
    cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
    header_val = request.headers.get(CSRF_HEADER_NAME)
    return (cookie_val, header_val)


def is_csrf_valid(request: "Request") -> bool:
    """True if cookie and header present and equal (constant-time compare)."""
    cookie_val, header_val = get_csrf_from_request(request)
    if not cookie_val or not header_val:
        return False
    return secrets.compare_digest(cookie_val, header_val)
