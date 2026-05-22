# backend/core/kernel/http/request_timing_middleware.py
# Feladat: ASGI middleware az API kérések időméréséhez, request metrikáihoz és timing logjaihoz. Válasz indításkor rögzíti a státuszt, teljes időt, DB statisztikákat és opcionális debug timing headereket, hiba esetén pedig exception eventet ír. Core HTTP observability komponens.
# Sárközi Mihály - 2026.05.21

import os
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from core.kernel.config.environment import is_production_env
from core.kernel.logging.request_timing import (
    clear_request_timing,
    get_db_stats,
    get_spans,
    init_request_timing,
    log_timing_debug,
    log_timing_info,
    log_timing_warning,
    record_request_metric,
)
from core.kernel.logging.observability import increment_metric, log_exception_event


class RequestTimingMiddleware:
    """ASGI: REQUEST IN/OUT log + X-Response-Time-Ms + X-Timing-Spans."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._debug_headers_enabled = not is_production_env(os.getenv("APP_ENV", "local"))

    @staticmethod
    def _path_group(path: str) -> str:
        parts = [item for item in str(path or "").split("/") if item]
        if len(parts) >= 2 and parts[0] == "api":
            return parts[1]
        if parts:
            return parts[0]
        return "root"

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
        init_request_timing()
        log_timing_debug("request.started", method=method, path=path)
        response_started = False

        async def send_wrapper(message: dict) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                status_code = message.get("status")
                record_request_metric(
                    status_code,
                    elapsed_ms,
                    method=method,
                    path_group=self._path_group(path),
                )
                message.setdefault("headers", [])
                spans = get_spans()
                db_query_count, db_query_total_ms = get_db_stats()
                if self._debug_headers_enabled:
                    message["headers"].append((b"x-response-time-ms", str(elapsed_ms).encode()))
                    if spans:
                        spans_str = ",".join(f"{n}:{ms}" for n, ms in spans)
                        message["headers"].append((b"x-timing-spans", spans_str.encode("utf-8")))
                state = scope.get("state") or {}
                log_timing_info(
                    "request.completed",
                    method=method,
                    path=path,
                    status_code=status_code,
                    total_ms=elapsed_ms,
                    tenant_slug=state.get("tenant_slug"),
                    tenant_id=state.get("tenant_id"),
                    user_id=getattr(state.get("user"), "id", None),
                    request_id=state.get("request_id"),
                    auth_outcome=state.get("auth_outcome"),
                    tenant_resolution_outcome=state.get("tenant_resolution_outcome"),
                    db_query_count=db_query_count,
                    db_query_total_ms=db_query_total_ms,
                    spans={name: ms for name, ms in spans},
                )
                if elapsed_ms > 1500:
                    log_timing_warning(
                        "request.slow",
                        method=method,
                        path=path,
                        status_code=status_code,
                        total_ms=elapsed_ms,
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            increment_metric("platform.request.error.count", 1.0)
            log_exception_event(
                "core.request_timing",
                "request.failed",
                exc,
                method=method,
                path=path,
                total_ms=elapsed_ms,
                response_started=response_started,
                tenant_slug=(scope.get("state") or {}).get("tenant_slug"),
                tenant_id=(scope.get("state") or {}).get("tenant_id"),
                user_id=getattr((scope.get("state") or {}).get("user"), "id", None),
                request_id=(scope.get("state") or {}).get("request_id"),
                auth_outcome=(scope.get("state") or {}).get("auth_outcome"),
                tenant_resolution_outcome=(scope.get("state") or {}).get("tenant_resolution_outcome"),
            )
            raise
        finally:
            clear_request_timing()

