# backend/core/kernel/logging/request_timing.py
# Feladat: Request scope timing spaneket és DB query statisztikákat gyűjt ContextVar alapon. A HTTP middleware, auth/tenant middleware és DB instrumentation innen rögzít részidőket, majd metrikát és strukturált timing logot ír. Core observability helper API hot-path teljesítményvizsgálathoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import contextvars
import logging
import os
from typing import List, Tuple

from core.kernel.config.environment import is_production_env

from core.kernel.logging.observability import increment_metric, log_structured_event, observe_metric

_timing_log = logging.getLogger("core.request_timing")

# Request-scoped span list: (name, ms). None = nincs aktív request timing.
_request_timing_spans: contextvars.ContextVar[List[Tuple[str, float]] | None] = contextvars.ContextVar(
    "request_timing_spans", default=None
)
_db_query_total_ms: contextvars.ContextVar[float] = contextvars.ContextVar(
    "db_query_total_ms", default=0.0
)
_db_query_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "db_query_count", default=0
)

_SPAN_METRICS = {
    "tenant_resolve": "platform.tenant.resolve.ms",
    "auth_resolve": "platform.auth.resolve.ms",
    "auth_total": "platform.auth.total.ms",
}


def init_request_timing() -> None:
    """Request elején hívja a middleware; üres listát állít be."""
    _request_timing_spans.set([])
    _db_query_total_ms.set(0.0)
    _db_query_count.set(0)


def record_span(name: str, ms: float) -> None:
    """Hot-path span rögzítése. Nop ha nincs init."""
    spans = _request_timing_spans.get()
    if spans is not None:
        spans.append((name, round(ms, 2)))
    metric_name = _SPAN_METRICS.get(name)
    if metric_name:
        observe_metric(metric_name, ms, unit="ms")


def record_request_metric(
    status_code: int | None,
    elapsed_ms: float,
    *,
    method: str | None = None,
    path_group: str | None = None,
) -> None:
    status_family = f"{int(status_code) // 100}xx" if status_code is not None else "unknown"
    tags = {
        "status_family": status_family,
        "method": (method or "").upper() or "UNKNOWN",
        "path_group": path_group or "api",
    }
    increment_metric("platform.request.count", 1.0, tags=tags)
    increment_metric("http_requests_total", 1.0, tags=tags)
    if status_family in {"2xx", "4xx", "5xx"}:
        increment_metric(f"platform.request.status.{status_family}.count", 1.0)
    observe_metric("platform.request.latency.ms", elapsed_ms, unit="ms", tags=tags)
    observe_metric("http_request_duration_seconds", float(elapsed_ms) / 1000.0, unit="seconds", tags=tags)


# Ez a függvény a(z) record_db_query logikáját valósítja meg.
def record_db_query(ms: float) -> None:
    spans = _request_timing_spans.get()
    if spans is None:
        return
    _db_query_total_ms.set(_db_query_total_ms.get() + ms)
    _db_query_count.set(_db_query_count.get() + 1)
    observe_metric("platform.db.query.ms", ms, unit="ms")
    observe_metric("platform.db.query.count", 1.0, unit="count")


def get_spans() -> List[Tuple[str, float]]:
    """Összegyűjtött span-ek."""
    spans = _request_timing_spans.get()
    if spans is None:
        return []
    out = list(spans)
    db_count = _db_query_count.get()
    if db_count:
        out.append(("db_query_total", round(_db_query_total_ms.get(), 2)))
        out.append(("db_query_count", float(db_count)))
    return out


# Ez a függvény visszaadja a(z) adatbázis stats logikáját.
def get_db_stats() -> tuple[int, float]:
    return _db_query_count.get(), round(_db_query_total_ms.get(), 2)


def clear_request_timing() -> None:
    """Tesztekhez: törli a kontextust."""
    try:
        _request_timing_spans.set(None)
        _db_query_total_ms.set(0.0)
        _db_query_count.set(0)
    except LookupError:
        pass


# Ez a függvény a(z) should_emit_timing_logs logikáját valósítja meg.
def should_emit_timing_logs() -> bool:
    return not is_production_env(os.getenv("APP_ENV", "local"))


# Ez a függvény a(z) log_timing_debug logikáját valósítja meg.
def log_timing_debug(event: str, **fields) -> None:
    if not should_emit_timing_logs() or not _timing_log.isEnabledFor(logging.DEBUG):
        return
    log_structured_event("core.request_timing", event, level=logging.DEBUG, **fields)


# Ez a függvény a(z) log_timing_info logikáját valósítja meg.
def log_timing_info(event: str, **fields) -> None:
    log_structured_event("core.request_timing", event, level=logging.INFO, **fields)


# Ez a függvény a(z) log_timing_warning logikáját valósítja meg.
def log_timing_warning(event: str, **fields) -> None:
    log_structured_event("core.request_timing", event, level=logging.WARNING, **fields)
