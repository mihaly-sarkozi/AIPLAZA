# apps/core/security/cookie_policy.py
# Refresh token cookie és session policy – multi-tenant, subdomain izoláció.
#
# Szabályok:
# - Refresh token CSAK HttpOnly, Secure, SameSite (JS nem éri el; csak HTTPS ha be van kapcsolva; SameSite = nem küldi másik site-nak).
# - Domain NINCS beállítva → host-only cookie: demo.local cookie NEM megy acme.local-ra (tenant → tenant nem szivárog).
# - Path=/api → csak /api kéréseknél küldi a böngésző.
#
# Frontend/integráció: access token NE legyen localStorage-ban (XSS miatt); csak memóriában. Refresh csak cookie-ból (HttpOnly).
# 2026.03 - Sárközi Mihály

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.responses import Response

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api"


def refresh_cookie_params(
    *,
    secure: bool,
    samesite: str = "lax",
    max_age: int | None = None,
) -> dict:
    """
    Refresh token cookie paraméterek. Domain szándékosan NINCS (host-only → subdomain izoláció).
    """
    return {
        "key": REFRESH_COOKIE_NAME,
        "path": REFRESH_COOKIE_PATH,
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "max_age": max_age,
    }


def set_refresh_cookie(
    response: "Response",
    value: str,
    *,
    secure: bool,
    samesite: str = "lax",
    max_age: int | None = None,
) -> None:
    """
    Refresh token cookie beállítása. HttpOnly, Secure, SameSite; domain nincs (host-only).
    """
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        value,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
    )


def clear_refresh_cookie(
    response: "Response",
    *,
    secure: bool,
    samesite: str = "lax",
) -> None:
    """
    Refresh token cookie törlése. Ugyanaz path/secure/samesite/httponly, hogy a böngésző biztosan törölje.
    Domain nincs (host-only, mint set-nél).
    """
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=secure,
        samesite=samesite,
        httponly=True,
    )
