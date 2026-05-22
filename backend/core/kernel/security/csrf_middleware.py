# backend/core/kernel/security/csrf_middleware.py
# Feladat: ASGI middleware a state-changing API kérések CSRF védelméhez. Ellenőrzi a CSRF cookie és header egyezését, kezeli a refresh origin/referer kivételt, valamint kihagyja az installer és token alapú channel endpointokat. Core HTTP security middleware, amelyet a middleware_registration köt be.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import os
import secrets
from urllib.parse import urlparse

from starlette.types import ASGIApp, Receive, Scope, Send

from core.kernel.config.config_loader import settings
from core.kernel.config.environment import is_production_env, normalize_app_env
from core.kernel.http.error_payloads import build_error_body_bytes_for_scope
from core.kernel.logging.observability import increment_metric, log_structured_event
from core.kernel.security.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    PLATFORM_ADMIN_CSRF_COOKIE_NAME,
)

_CSRF_DISABLE_ALLOWED_ENVS = {"local", "test"}


def _record_csrf_rejection(scope: Scope, *, reason: str) -> None:
    increment_metric("csrf_rejections_total", 1.0, tags={"reason": reason})
    log_structured_event(
        "core.security.csrf",
        "csrf.rejected",
        level=logging.WARNING,
        method=str(scope.get("method") or ""),
        path=str(scope.get("path") or ""),
        reason=reason,
    )


def csrf_disabled_by_env() -> bool:
    if os.environ.get("DISABLE_CSRF") != "1":
        return False
    env = normalize_app_env(os.getenv("APP_ENV") or "local")
    return env in _CSRF_DISABLE_ALLOWED_ENVS


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

    if not origin and not referer:
        return not is_production_env(os.getenv("APP_ENV", "local"))

    if origin and _origin_netloc(origin) not in allowed_netlocs:
        return False
    if referer and _origin_netloc(referer) not in allowed_netlocs:
        return False
    return True


class CSRFMiddleware:
    """Reject POST/PUT/PATCH/DELETE to /api/* when X-CSRF-Token header does not match csrf_token cookie."""

    def __init__(self, app: ASGIApp, *, skip_path: str = "/api/auth/csrf-token") -> None:
        self.app = app
        self.skip_path = skip_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if csrf_disabled_by_env():
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")

        if method not in ("POST", "PUT", "PATCH", "DELETE") or not path.startswith("/api"):
            await self.app(scope, receive, send)
            return
        if path == "/api/auth/refresh" or path == "/api/platform-admin/auth/refresh":
            if not _refresh_origin_allowed(scope):
                _record_csrf_rejection(scope, reason="invalid_refresh_origin")
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": build_error_body_bytes_for_scope(
                        scope=scope,
                        status_code=403,
                        code="CSRF_REJECTED",
                        message="Access denied.",
                        detail="Refresh origin or referer invalid",
                    ),
                })
                return
            await self.app(scope, receive, send)
            return
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
            _record_csrf_rejection(scope, reason="missing_or_invalid_token")
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": build_error_body_bytes_for_scope(
                    scope=scope,
                    status_code=403,
                    code="CSRF_REJECTED",
                    message="Access denied.",
                    detail="CSRF token missing or invalid",
                ),
            })
            return

        await self.app(scope, receive, send)

