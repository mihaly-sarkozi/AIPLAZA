# apps/core/middleware/csrf_middleware.py
# CSRF validation for state-changing requests (POST/PUT/PATCH/DELETE). Skip GET /api/auth/csrf-token.
# 2026 - Sárközi Mihály

from __future__ import annotations

import os
import secrets

from starlette.types import ASGIApp, Receive, Scope, Send

from apps.core.security.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


def _get_cookie(scope: Scope, name: str) -> str | None:
    cookie_header = _get_header(scope, "Cookie")
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part[len(name) + 1 :].strip().strip('"')
    return None


class CSRFMiddleware:
    """Reject POST/PUT/PATCH/DELETE to /api/* when X-CSRF-Token header does not match csrf_token cookie."""

    def __init__(self, app: ASGIApp, *, skip_path: str = "/api/auth/csrf-token") -> None:
        self.app = app
        self.skip_path = skip_path

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
        if path == self.skip_path or path.startswith("/api/public/"):
            # Nyilvános végpontok (check-slug, demo-signup): nincs bejelentkezett session, CSRF kivétel
            await self.app(scope, receive, send)
            return

        cookie_val = _get_cookie(scope, CSRF_COOKIE_NAME)
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
