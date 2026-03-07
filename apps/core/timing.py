# apps/core/timing.py
# Hot-path bontott timing: request szintű span-ek (token_verify, allowlist_check, user_cache_*, user_db_fetch, refresh_session_lookup, email_send).
# ContextVar: a request első middleware-je inicializálja; bárki record_span()-nel rögzít; a válasz előtt log + X-Timing-Spans header.
# 2026.03 - Sárközi Mihály

from __future__ import annotations

import contextvars
import logging
from typing import List, Tuple

_log = logging.getLogger(__name__)

# Request-scoped span list: (name, ms). None = nincs aktív request timing.
_request_timing_spans: contextvars.ContextVar[List[Tuple[str, float]] | None] = contextvars.ContextVar(
    "request_timing_spans", default=None
)


def init_request_timing() -> None:
    """Request elején hívja a middleware; üres listát állít be."""
    _request_timing_spans.set([])


def record_span(name: str, ms: float) -> None:
    """Hot-path span rögzítése (pl. token_verify, allowlist_check, user_db_fetch). Nop ha nincs init."""
    spans = _request_timing_spans.get()
    if spans is not None:
        spans.append((name, round(ms, 2)))


def get_spans() -> List[Tuple[str, float]]:
    """Összegyűjtött span-ek (middleware: log + header)."""
    spans = _request_timing_spans.get()
    return list(spans) if spans is not None else []


def clear_request_timing() -> None:
    """Tesztekhez: törli a kontextust."""
    try:
        _request_timing_spans.set(None)
    except LookupError:
        pass
