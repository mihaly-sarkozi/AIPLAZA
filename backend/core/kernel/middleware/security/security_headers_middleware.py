# Canonical security middleware location.

from __future__ import annotations

import os

_CSP_DIRECTIVES = (
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
)
_CSP_HEADER_VALUE = "; ".join(_CSP_DIRECTIVES)
_HSTS_HEADER_VALUE = b"max-age=31536000; includeSubDomains"


# Ez a függvény visszaadja a(z) header logikáját.
def _get_header(scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1").strip()
    return None


# Ez a függvény a(z) is_https_request logikáját valósítja meg.
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

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, app):
        self.app = app
        self._hsts_enabled = os.getenv("APP_ENV", "dev").strip().lower() == "prod"

    # Ez az aszinkron metódus a Python-specifikus speciális működést valósítja meg.
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        send_hsts = self._hsts_enabled and _is_https_request(scope)

        # Ez az aszinkron függvény a(z) send_with_headers logikáját valósítja meg.
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                if send_hsts:
                    headers.append((b"strict-transport-security", _HSTS_HEADER_VALUE))
                headers.append((b"content-security-policy", _CSP_HEADER_VALUE.encode("utf-8")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
