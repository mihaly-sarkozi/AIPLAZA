# apps/core/middleware/correlation_id_middleware.py
# Request-id / correlation_id a scope.state-ra (X-Request-ID header vagy generált UUID).
# ASGI middleware – alacsonyabb overhead mint BaseHTTPMiddleware.
# 2026.03 - Sárközi Mihály

import uuid
from starlette.types import ASGIApp, Receive, Scope, Send


def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


class CorrelationIdMiddleware:
    """ASGI: Beállítja scope["state"]["correlation_id"]; válaszban X-Request-ID header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        correlation_id = _get_header(scope, "X-Request-ID") or str(uuid.uuid4())
        state["correlation_id"] = correlation_id

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", correlation_id.encode()))
            await send(message)

        await self.app(scope, receive, send_wrapper)
