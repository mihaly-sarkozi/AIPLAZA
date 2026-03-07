# apps/core/middleware/request_timing_middleware.py
# Kérés időmérés + X-Response-Time-Ms + bontott hot-path span-ek (X-Timing-Spans, log).
# 2026.03 - Sárközi Mihály

import logging
import sys
import time
from datetime import datetime, timezone
from starlette.types import ASGIApp, Receive, Scope, Send

from apps.core.timing import get_spans

_log = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _api_timing(msg: str) -> None:
    print(f"[TIME] {_ts()} {msg}", file=sys.stderr, flush=True)


class RequestTimingMiddleware:
    """ASGI: REQUEST IN/OUT log + X-Response-Time-Ms + X-Timing-Spans (token_verify, allowlist_check, user_load, stb.)."""

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
                # Bontott timing span-ek (token_verify, allowlist_check, user_cache_*, user_db_fetch, refresh_*, stb.)
                spans = get_spans()
                if spans:
                    spans_str = ",".join(f"{n}:{ms}" for n, ms in spans)
                    message["headers"].append((b"x-timing-spans", spans_str.encode("utf-8")))
                    correlation_id = (scope.get("state") or {}).get("correlation_id")
                    _log.info("timing_spans", extra={"correlation_id": correlation_id, "path": path, "spans": dict(spans), "total_ms": elapsed_ms})
                _api_timing(f"REQUEST OUT  {method} {path}  total={time.monotonic() - t0:.3f}s")
            await send(message)

        await self.app(scope, receive, send_wrapper)
