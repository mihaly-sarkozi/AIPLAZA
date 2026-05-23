# backend/core/kernel/http/correlation_id_middleware.py
# Feladat: ASGI middleware, amely minden HTTP kéréshez correlation_id és request_id értéket állít be. Beolvassa a biztonságos inbound header értékeket vagy újat generál, majd a választ is ellátja ezekkel a fejlécekkel és observability contextet köt a kéréshez. Core HTTP observability komponens.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from core.kernel.logging.observability import bind_observability_context, reset_observability_context

_VALID_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _normalize_id(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if not _VALID_ID.fullmatch(raw):
        return None
    return raw


def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


class CorrelationIdMiddleware:
    """ASGI: Beállítja scope['state']['correlation_id']; válaszban X-Request-ID header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        inbound_correlation = _normalize_id(_get_header(scope, "X-Correlation-ID"))
        inbound_request_id = _normalize_id(_get_header(scope, "X-Request-ID"))
        correlation_id = inbound_correlation or inbound_request_id or str(uuid.uuid4())
        request_id = inbound_request_id or correlation_id
        state["correlation_id"] = correlation_id
        state["request_id"] = request_id
        token = bind_observability_context(
            correlation_id=correlation_id,
            request_id=request_id,
        )

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode()))
                message["headers"].append((b"x-correlation-id", correlation_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            reset_observability_context(token)

