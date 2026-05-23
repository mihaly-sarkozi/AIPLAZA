# backend/core/kernel/security/security_headers_middleware.py
# Feladat: ASGI middleware, amely alap security headereket ad minden HTTP válaszhoz. Beállítja a frame, content-type, XSS, referrer policy, CSP és production HTTPS esetén HSTS headereket. Core HTTP security middleware, amely a globális middleware lánc része.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os

from core.kernel.config.environment import is_production_env

from core.kernel.config.config_loader import settings

_CSP_BASE_SOURCES: dict[str, list[str]] = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "connect-src": ["'self'"],
    "frame-ancestors": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
}
_HSTS_HEADER_VALUE = b"max-age=31536000; includeSubDomains"
_PERMISSIONS_POLICY_HEADER_VALUE = (
    b"geolocation=(), microphone=(), camera=(), payment=(), usb=(), browsing-topics=()"
)


def _split_sources(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _csp_header_value() -> str:
    directives = {name: list(values) for name, values in _CSP_BASE_SOURCES.items()}
    extra_connect = _split_sources(getattr(settings, "security_csp_extra_connect_src", ""))
    extra_img = _split_sources(getattr(settings, "security_csp_extra_img_src", ""))
    extra_frame = _split_sources(getattr(settings, "security_csp_extra_frame_src", ""))
    directives["connect-src"].extend(extra_connect)
    directives["img-src"].extend(extra_img)
    if extra_frame:
        directives["frame-src"] = ["'self'", *extra_frame]
    return "; ".join(f"{name} {' '.join(values)}" for name, values in directives.items())


def _get_header(scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1").strip()
    return None


def _is_https_request(scope) -> bool:
    forwarded_proto = _get_header(scope, b"x-forwarded-proto")
    if forwarded_proto:
        first_proto = forwarded_proto.split(",", 1)[0].strip().lower()
        if first_proto:
            return first_proto == "https"

    forwarded = _get_header(scope, b"forwarded")
    if forwarded:
        first_segment = forwarded.split(",", 1)[0]
        for part in first_segment.split(";"):
            name, _, value = part.strip().partition("=")
            if name.lower() == "proto":
                return value.strip().strip('"').lower() == "https"

    return str(scope.get("scheme") or "").lower() == "https"


class SecurityHeadersMiddleware:
    """CSP és security headerek minden HTTP válaszra."""

    def __init__(self, app):
        self.app = app
        self._hsts_enabled = is_production_env(os.getenv("APP_ENV", "local"))
        self._csp_header_value = _csp_header_value().encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        send_hsts = self._hsts_enabled and _is_https_request(scope)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                headers.append((b"permissions-policy", _PERMISSIONS_POLICY_HEADER_VALUE))
                if send_hsts:
                    headers.append((b"strict-transport-security", _HSTS_HEADER_VALUE))
                headers.append((b"content-security-policy", self._csp_header_value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

