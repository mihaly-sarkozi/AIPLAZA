# Canonical security middleware location.

from __future__ import annotations

import os
import secrets
from urllib.parse import urlparse

from starlette.types import ASGIApp, Receive, Scope, Send

from core.kernel.config.config_loader import settings
from core.kernel.security.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    PLATFORM_ADMIN_CSRF_COOKIE_NAME,
)


# Ez a függvény visszaadja a(z) header logikáját.
def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


def _is_channel_token_request(scope: Scope, path: str) -> bool:
    if not path.startswith("/api/channel/"):
        return False
    authorization = str(_get_header(scope, "Authorization") or "").strip()
    if authorization.lower().startswith("bearer ") and authorization[7:].strip():
        return True
    api_key = str(_get_header(scope, "X-API-Key") or "").strip()
    return bool(api_key)


# Ez a függvény visszaadja a(z) cookie logikáját.
def _get_cookie(scope: Scope, name: str) -> str | None:
    cookie_header = _get_header(scope, "Cookie")
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part[len(name) + 1 :].strip().strip('"')
    return None


def _request_host(scope: Scope) -> str:
    return str(_get_header(scope, "Host") or "").strip().lower()


def _origin_netloc(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    return str(parsed.netloc or "").strip().lower()


def _configured_refresh_origin_netlocs() -> set[str]:
    explicit = str(getattr(settings, "csrf_refresh_allowed_origins", "") or "").strip()
    cors = str(getattr(settings, "cors_origins", "") or "").strip()
    frontend_base = str(getattr(settings, "frontend_base_url", "") or "").strip()
    candidates: list[str] = []
    if explicit:
        candidates.extend([part.strip() for part in explicit.split(",") if part.strip()])
    else:
        candidates.extend([part.strip() for part in cors.split(",") if part.strip()])
    if frontend_base:
        candidates.append(frontend_base)
    netlocs: set[str] = set()
    for candidate in candidates:
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
        netloc = str(parsed.netloc or "").strip().lower()
        if netloc:
            netlocs.add(netloc)
    return netlocs


def _refresh_origin_allowed(scope: Scope) -> bool:
    host = _request_host(scope)
    if not host:
        return False
    allowed_netlocs = {host, *_configured_refresh_origin_netlocs()}
    origin = str(_get_header(scope, "Origin") or "").strip()
    referer = str(_get_header(scope, "Referer") or "").strip()

    # Productionben a refresh endpointet csak browser same-origin kérés hívhatja.
    if not origin and not referer:
        return (os.getenv("APP_ENV", "dev") or "dev").strip().lower() != "prod"

    if origin and _origin_netloc(origin) not in allowed_netlocs:
        return False
    if referer and _origin_netloc(referer) not in allowed_netlocs:
        return False
    return True


class CSRFMiddleware:
    """Reject POST/PUT/PATCH/DELETE to /api/* when X-CSRF-Token header does not match csrf_token cookie."""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, app: ASGIApp, *, skip_path: str = "/api/auth/csrf-token") -> None:
        self.app = app
        self.skip_path = skip_path

    # Ez az aszinkron metódus a Python-specifikus speciális működést valósítja meg.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if os.environ.get("DISABLE_CSRF") == "1":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")

        if method not in ("POST", "PUT", "PATCH", "DELETE") or not path.startswith("/api"):
            await self.app(scope, receive, send)
            return
        if path == "/api/auth/refresh" or path == "/api/platform-admin/auth/refresh":
            if not _refresh_origin_allowed(scope):
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"detail":"Refresh origin or referer invalid"}',
                })
                return
            await self.app(scope, receive, send)
            return
        # Refresh: HttpOnly refresh cookie a titok; 401 utáni újrapróbánál a kliens CSRF-je nélkül is fusson.
        if (
            path == self.skip_path
            or path.startswith("/api/installer/")
            or _is_channel_token_request(scope, path)
        ):
            await self.app(scope, receive, send)
            return

        csrf_cookie_name = PLATFORM_ADMIN_CSRF_COOKIE_NAME if path.startswith("/api/platform-admin/") else CSRF_COOKIE_NAME
        cookie_val = _get_cookie(scope, csrf_cookie_name)
        header_val = _get_header(scope, CSRF_HEADER_NAME)
        if not cookie_val or not header_val or not secrets.compare_digest(cookie_val, header_val):
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail":"CSRF token missing or invalid"}',
            })
            return

        await self.app(scope, receive, send)
