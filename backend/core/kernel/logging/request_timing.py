# Hot-path bontott timing: request szintű span-ek (token_verify, allowlist_check, user_cache_*, user_db_fetch, refresh_session_lookup, email_send).

from __future__ import annotations

import contextvars
import logging
import os
from typing import List, Tuple

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


def record_request_metric(status_code: int | None, elapsed_ms: float) -> None:
    status_family = f"{int(status_code) // 100}xx" if status_code is not None else "unknown"
    increment_metric("platform.request.count", 1.0, tags={"status_family": status_family})
    observe_metric("platform.request.latency.ms", elapsed_ms, unit="ms", tags={"status_family": status_family})


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
    return os.getenv("APP_ENV", "dev").strip().lower() != "prod"


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
