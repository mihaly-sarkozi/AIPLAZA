# apps/core/middleware/request_timing_middleware.py
# Kérés időmérés + X-Response-Time-Ms header. ASGI – alacsonyabb overhead.
# 2026.03 - Sárközi Mihály

import sys
import time
from datetime import datetime, timezone
from starlette.types import ASGIApp, Receive, Scope, Send


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _api_timing(msg: str) -> None:
    print(f"[TIME] {_ts()} {msg}", file=sys.stderr, flush=True)


class RequestTimingMiddleware:
    """ASGI: REQUEST IN/OUT log + X-Response-Time-Ms válasz header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "") or ""
        if not path.startswith("/api"):
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "")
        t0 = time.monotonic()
        _api_timing(f"REQUEST IN   {method} {path}")

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                message.setdefault("headers", [])
                message["headers"].append((b"x-response-time-ms", str(elapsed_ms).encode()))
                _api_timing(f"REQUEST OUT  {method} {path}  total={time.monotonic() - t0:.3f}s")
            await send(message)

        await self.app(scope, receive, send_wrapper)
