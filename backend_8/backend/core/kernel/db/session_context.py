# backend/core/kernel/db/session_context.py
# Feladat: A DB session context manager, proxy és tenant search_path beállítás közös helper modulja. A SessionProxy tranzakcióban a commitot flush-ra fordítja, a SessionContext pedig gondoskodik a session lezárásáról vagy újrahasznosításáról. A session.py használja, ezért belső core DB runtime helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from sqlalchemy import text

from core.modules.tenant.context.tenant_context import current_tenant_schema


def apply_search_path(session, schema: str | None) -> None:
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        return
    if schema:
        safe = "".join(c for c in schema if c.isalnum() or c in "_-")
        if safe == schema:
            session.execute(text(f'SET search_path TO "{safe}"'))
            return
    session.execute(text("SET search_path TO public"))


class SessionProxy:
    __slots__ = ("_session", "_commit_is_flush")

    def __init__(self, session, *, commit_is_flush: bool):
        self._session = session
        self._commit_is_flush = commit_is_flush

    def commit(self):
        if self._commit_is_flush:
            self._session.flush()
            return
        self._session.commit()

    def rollback(self):
        self._session.rollback()

    def refresh(self, instance, *args, **kwargs):
        apply_search_path(self._session, current_tenant_schema.get(None))
        return self._session.refresh(instance, *args, **kwargs)

    def close(self):
        return None

    def __getattr__(self, name):
        return getattr(self._session, name)


class SessionContext:
    __slots__ = ("_session", "_schema", "_close_on_exit", "_commit_is_flush")

    def __init__(self, session, schema, *, close_on_exit: bool, commit_is_flush: bool):
        self._session = session
        self._schema = schema
        self._close_on_exit = close_on_exit
        self._commit_is_flush = commit_is_flush

    def __enter__(self):
        if self._close_on_exit:
            apply_search_path(self._session, self._schema)
        return SessionProxy(self._session, commit_is_flush=self._commit_is_flush)

    def __exit__(self, *args):
        if self._close_on_exit:
            self._session.close()


__all__ = ["SessionContext", "SessionProxy", "apply_search_path"]
