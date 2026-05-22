# backend/core/kernel/db/instrumentation.py
# Feladat: SQLAlchemy engine szintű megfigyelhetőségi hookokat telepít. Méri a query futási időt, DB hibáknál metrikát növel és strukturált kivétel eseményt naplóz. A session factory hívja, ezért általános core observability adapter a DB réteghez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import time

from sqlalchemy import event

from core.kernel.logging.observability import increment_metric, log_exception_event
from core.kernel.logging.request_timing import record_db_query


def install_engine_instrumentation(engine) -> None:
    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    event.listen(engine, "handle_error", _handle_db_error)


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.monotonic())


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    starts = conn.info.get("query_start_time") or []
    if not starts:
        return
    started = starts.pop()
    record_db_query((time.monotonic() - started) * 1000)


def _handle_db_error(exception_context):
    original = getattr(exception_context, "original_exception", None)
    if original is None:
        return
    statement = getattr(exception_context, "statement", None)
    try:
        increment_metric("platform.db.error.count", 1.0)
        log_exception_event(
            "core.db",
            "db_error",
            original,
            statement_preview=(str(statement)[:240] if statement else None),
        )
    except Exception:
        return


__all__ = ["install_engine_instrumentation"]
