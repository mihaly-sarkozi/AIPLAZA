# backend/core/kernel/security/cookie_policy.py
# Feladat: Refresh, platform-admin refresh, WebSocket token és channel chat session cookie policy helperjeit tartalmazza. A cookie-k host-only, HttpOnly, path-szűrt és konfigurált Secure/SameSite szabályokkal kerülnek beállításra, hogy tenantok között ne szivárogjanak. Core HTTP security helper, amelyet auth és chat routerek használnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.responses import Response

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api"
PLATFORM_ADMIN_REFRESH_COOKIE_NAME = "platform_admin_refresh_token"
PLATFORM_ADMIN_REFRESH_COOKIE_PATH = "/api/platform-admin"

# WebSocket auth: rövid életű cookie (nem kerül query stringbe → nem logolódik)
WS_TOKEN_COOKIE_NAME = "ws_token"
WS_TOKEN_MAX_AGE_SEC = 120  # 2 perc – csak a WS handshake-ig kell
CHANNEL_CHAT_SESSION_COOKIE_NAME = "channel_chat_session"
CHANNEL_CHAT_SESSION_MAX_AGE_SEC = 86400  # 24 óra


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


def set_platform_admin_refresh_cookie(
    response: "Response",
    value: str,
    *,
    secure: bool,
    samesite: str = "lax",
    max_age: int | None = None,
) -> None:
    response.set_cookie(
        PLATFORM_ADMIN_REFRESH_COOKIE_NAME,
        value,
        path=PLATFORM_ADMIN_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
    )


def clear_platform_admin_refresh_cookie(
    response: "Response",
    *,
    secure: bool,
    samesite: str = "lax",
) -> None:
    response.delete_cookie(
        PLATFORM_ADMIN_REFRESH_COOKIE_NAME,
        path=PLATFORM_ADMIN_REFRESH_COOKIE_PATH,
        secure=secure,
        samesite=samesite,
        httponly=True,
    )


def set_ws_token_cookie(
    response: "Response",
    value: str,
    *,
    secure: bool,
    samesite: str = "lax",
    max_age: int = WS_TOKEN_MAX_AGE_SEC,
) -> None:
    """
    WebSocket auth: rövid életű HttpOnly cookie. A token NEM kerül query stringbe → nem logolódik.
    Path=/api, hogy a /chat/ws upgrade ugyanazon a path alatt kapta.
    """
    response.set_cookie(
        WS_TOKEN_COOKIE_NAME,
        value,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
    )


def set_channel_chat_session_cookie(
    response: "Response",
    value: str,
    *,
    secure: bool,
    samesite: str = "lax",
    max_age: int = CHANNEL_CHAT_SESSION_MAX_AGE_SEC,
) -> None:
    """
    Embedded channel chat session-azonosító cookie.
    Host-only + HttpOnly, hogy a session kulcs ne legyen JS-ből olvasható.
    """
    response.set_cookie(
        CHANNEL_CHAT_SESSION_COOKIE_NAME,
        value,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
    )
