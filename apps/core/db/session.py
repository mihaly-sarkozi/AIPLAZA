# apps/core/db/session.py
# Session factory: current_tenant_schema alapján SET search_path.
# - Ha schema be van állítva (pl. "demo") → tenant séma (users, sessions, stb.).
# - Ha schema None (pl. middleware executor szál, vagy még nincs tenant) → public (tenants, tenant_domains – nem tenant-scoped user adat, nincs szivárgás).
# 2026.02.14 - Sárközi Mihály

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from apps.core.db.tenant_context import current_tenant_schema


def make_session_factory(dsn: str, *, pool_pre_ping: bool = True):
    engine = create_engine(dsn, future=True, pool_pre_ping=pool_pre_ping)
    inner = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    class _SessionContext:
        __slots__ = ("_session", "_schema")

        def __init__(self, session, schema):
            self._session = session
            self._schema = schema

        def __enter__(self):
            if self._schema:
                # Sémanév: betű, szám, aláhúzás, kötőjel (pl. ferike-hu) – PostgreSQL idézett azonosító
                safe = "".join(c for c in self._schema if c.isalnum() or c in "_-")
                if safe == self._schema:
                    self._session.execute(text(f'SET search_path TO "{safe}"'))
            else:
                # Nincs tenant context (pl. middleware get_by_slug executor szál): public (tenant lista, nincs user adat).
                self._session.execute(text("SET search_path TO public"))
            return self._session

        def __exit__(self, *args):
            self._session.close()

    def factory():
        session = inner()
        schema = current_tenant_schema.get(None)
        return _SessionContext(session, schema)

    return factory
