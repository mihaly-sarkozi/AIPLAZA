# backend/core/kernel/db/session.py
# Feladat: Tenant-aware SQLAlchemy session factoryt ad a backend számára. A current_tenant_schema alapján állítja a search_path-ot, kezeli az ambient tranzakciós session újrahasznosítást, és beköti az engine instrumentationt. A bootstrap infrastruktúra és integrációs tesztek használják, ezért ez általános core DB runtime elem.
# Sárközi Mihály - 2026.05.21

from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.kernel.db.instrumentation import install_engine_instrumentation
from core.kernel.db.session_context import SessionContext, SessionProxy, apply_search_path

_current_db_session: ContextVar[object | None] = ContextVar("current_db_session", default=None)
_transaction_depth: ContextVar[int] = ContextVar("db_transaction_depth", default=0)

class _SessionFactory:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, dsn: str, *, pool_pre_ping: bool = True):
        from core.kernel.config.config_loader import settings

        self._engine = create_engine(dsn, **_engine_kwargs(dsn, settings=settings, pool_pre_ping=pool_pre_ping))
        if self._engine.dialect.name == "sqlite":
            from core.modules.tenant.models.tenant_orm import TenantORM

            TenantORM.__table__.create(self._engine, checkfirst=True)
        install_engine_instrumentation(self._engine)
        self._inner = sessionmaker(bind=self._engine, expire_on_commit=False, autoflush=False)

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __call__(self):
        shared_session = _current_db_session.get(None)
        if shared_session is not None:
            return SessionContext(
                shared_session,
                current_tenant_schema.get(None),
                close_on_exit=False,
                commit_is_flush=True,
            )
        session = self._inner()
        return SessionContext(
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
                yield SessionProxy(shared_session, commit_is_flush=True)
            finally:
                _transaction_depth.reset(depth_token)
            return

        session = self._inner()
        schema = current_tenant_schema.get(None)
        apply_search_path(session, schema)
        session_token = _current_db_session.set(session)
        depth_token = _transaction_depth.set(1)
        try:
            yield SessionProxy(session, commit_is_flush=True)
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


def _engine_kwargs(dsn: str, *, settings: object, pool_pre_ping: bool) -> dict[str, object]:
    kwargs: dict[str, object] = {"future": True, "pool_pre_ping": pool_pre_ping}
    if make_url(dsn).get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
        kwargs["execution_options"] = {"schema_translate_map": {"public": None}}
        return kwargs
    kwargs.update(
        {
            "pool_size": max(1, int(getattr(settings, "database_pool_size", 10))),
            "max_overflow": max(0, int(getattr(settings, "database_max_overflow", 20))),
            "pool_timeout": max(1, int(getattr(settings, "database_pool_timeout_sec", 30))),
            "pool_recycle": max(1, int(getattr(settings, "database_pool_recycle_sec", 1800))),
        }
    )
    return kwargs
