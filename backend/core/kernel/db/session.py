# Session factory: current_tenant_schema alapján SET search_path.
# - Ha schema be van állítva (pl. "demo") → tenant séma (users, sessions, stb.).
# - Ha schema None (pl. middleware executor szál, vagy még nincs tenant) → public (tenants, tenant_domains – nem tenant-scoped user adat, nincs szivárgás).
# - Tranzakciós üzleti flow-knál ugyanaz a session újrahasznosítható ambient módon, így a repo-k commitja csak flush lesz.
# 2026.02.14 - Sárközi Mihály

from contextlib import contextmanager
from contextvars import ContextVar
import time

from sqlalchemy import create_engine, text
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from core.extensions.tenant.context.tenant_context import current_tenant_schema
from core.kernel.logging.observability import increment_metric, log_exception_event
from core.kernel.logging.request_timing import record_db_query

_current_db_session: ContextVar[object | None] = ContextVar("current_db_session", default=None)
_transaction_depth: ContextVar[int] = ContextVar("db_transaction_depth", default=0)


# Ez a függvény a(z) apply_search_path logikáját valósítja meg.
def _apply_search_path(session, schema: str | None) -> None:
    if schema:
        safe = "".join(c for c in schema if c.isalnum() or c in "_-")
        if safe == schema:
            session.execute(text(f'SET search_path TO "{safe}"'))
            return
    session.execute(text("SET search_path TO public"))


class _SessionProxy:
    __slots__ = ("_session", "_commit_is_flush")

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session, *, commit_is_flush: bool):
        self._session = session
        self._commit_is_flush = commit_is_flush

    # Ez a metódus a(z) commit logikáját valósítja meg.
    def commit(self):
        if self._commit_is_flush:
            self._session.flush()
            return
        self._session.commit()

    # Ez a metódus a(z) rollback logikáját valósítja meg.
    def rollback(self):
        self._session.rollback()

    # Ez a metódus a(z) refresh logikáját valósítja meg.
    def refresh(self, instance, *args, **kwargs):
        _apply_search_path(self._session, current_tenant_schema.get(None))
        return self._session.refresh(instance, *args, **kwargs)

    # Ez a metódus a(z) close logikáját valósítja meg.
    def close(self):
        return None

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __getattr__(self, name):
        return getattr(self._session, name)


class _SessionContext:
    __slots__ = ("_session", "_schema", "_close_on_exit", "_commit_is_flush")

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session, schema, *, close_on_exit: bool, commit_is_flush: bool):
        self._session = session
        self._schema = schema
        self._close_on_exit = close_on_exit
        self._commit_is_flush = commit_is_flush

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __enter__(self):
        if self._close_on_exit:
            _apply_search_path(self._session, self._schema)
        return _SessionProxy(self._session, commit_is_flush=self._commit_is_flush)

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __exit__(self, *args):
        if self._close_on_exit:
            self._session.close()


class _SessionFactory:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, dsn: str, *, pool_pre_ping: bool = True):
        from core.kernel.config.config_loader import settings

        self._engine = create_engine(
            dsn,
            future=True,
            pool_pre_ping=pool_pre_ping,
            pool_size=max(1, int(getattr(settings, "database_pool_size", 10))),
            max_overflow=max(0, int(getattr(settings, "database_max_overflow", 20))),
            pool_timeout=max(1, int(getattr(settings, "database_pool_timeout_sec", 30))),
            pool_recycle=max(1, int(getattr(settings, "database_pool_recycle_sec", 1800))),
        )
        event.listen(self._engine, "before_cursor_execute", self._before_cursor_execute)
        event.listen(self._engine, "after_cursor_execute", self._after_cursor_execute)
        event.listen(self._engine, "handle_error", self._handle_db_error)
        self._inner = sessionmaker(bind=self._engine, expire_on_commit=False, autoflush=False)

    # Ez a metódus a(z) before_cursor_execute logikáját valósítja meg.
    @staticmethod
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.monotonic())

    # Ez a metódus a(z) after_cursor_execute logikáját valósítja meg.
    @staticmethod
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get("query_start_time") or []
        if not starts:
            return
        started = starts.pop()
        record_db_query((time.monotonic() - started) * 1000)

    @staticmethod
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

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __call__(self):
        shared_session = _current_db_session.get(None)
        if shared_session is not None:
            return _SessionContext(
                shared_session,
                current_tenant_schema.get(None),
                close_on_exit=False,
                commit_is_flush=True,
            )
        session = self._inner()
        return _SessionContext(
            session,
            current_tenant_schema.get(None),
            close_on_exit=True,
            commit_is_flush=False,
        )

    # Ez a metódus a(z) transaction logikáját valósítja meg.
    @contextmanager
    def transaction(self):
        shared_session = _current_db_session.get(None)
        if shared_session is not None:
            depth_token = _transaction_depth.set(_transaction_depth.get() + 1)
            try:
                yield _SessionProxy(shared_session, commit_is_flush=True)
            finally:
                _transaction_depth.reset(depth_token)
            return

        session = self._inner()
        schema = current_tenant_schema.get(None)
        _apply_search_path(session, schema)
        session_token = _current_db_session.set(session)
        depth_token = _transaction_depth.set(1)
        try:
            yield _SessionProxy(session, commit_is_flush=True)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            _transaction_depth.reset(depth_token)
            _current_db_session.reset(session_token)
            session.close()

    # Ez a metódus a(z) engine logikáját valósítja meg.
    @property
    def engine(self):
        return self._engine


# Ez a függvény a(z) make_session_factory logikáját valósítja meg.
def make_session_factory(dsn: str, *, pool_pre_ping: bool = True):
    return _SessionFactory(dsn, pool_pre_ping=pool_pre_ping)
