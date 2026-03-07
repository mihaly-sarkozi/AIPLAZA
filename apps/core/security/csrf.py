# apps/core/security/csrf.py
# CSRF double-submit: token in cookie + X-CSRF-Token header; state-changing requests must match.
# 2026 - Sárközi Mihály

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_PATH = "/api"


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
