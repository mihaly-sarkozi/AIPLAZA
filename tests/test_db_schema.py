# tests/test_db_schema.py
"""DB séma tesztek: public és demo táblák/szerkezet létezik és megfelelő."""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Projekt gyökér (config, apps importok)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# .env betöltése (tesztek futtatásakor a cwd lehet tests/)
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)


def _get_engine() -> Engine | None:
    try:
        from config.settings import settings
        url = getattr(settings, "database_url", None) or os.environ.get("DATABASE_URL")
        if not url or "postgresql" not in url.split(":")[0].lower():
            return None
        return create_engine(url, future=True)
    except Exception:
        return None


@pytest.fixture(scope="module")
def db_engine():
    """DB engine; ha nincs elérhető DB, skip."""
    engine = _get_engine()
    if engine is None:
        pytest.skip("Nincs database_url (PostgreSQL)")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"DB nem elérhető: {e}")
    return engine


def _table_exists(engine: Engine, schema: str, table: str) -> bool:
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :name"
            ),
            {"schema": schema, "name": table},
        )
        return r.scalar() is not None


def _columns(engine: Engine, schema: str, table: str) -> set[str]:
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :name"
            ),
            {"schema": schema, "name": table},
        )
        return {row[0] for row in r}


def _schema_exists(engine: Engine, schema: str) -> bool:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :n"),
            {"n": schema},
        )
        return r.scalar() is not None


# --- Public táblák ---

def test_public_tenants_exists(db_engine):
    assert _table_exists(db_engine, "public", "tenants"), "public.tenants tábla hiányzik"


def test_public_tenants_structure(db_engine):
    cols = _columns(db_engine, "public", "tenants")
    required = {"id", "slug", "name", "created_at", "security_version", "is_active"}
    missing = required - cols
    assert not missing, f"public.tenants hiányzó oszlopok: {missing}"


def test_public_tenant_configs_exists(db_engine):
    assert _table_exists(db_engine, "public", "tenant_configs"), "public.tenant_configs tábla hiányzik"


def test_public_tenant_configs_structure(db_engine):
    cols = _columns(db_engine, "public", "tenant_configs")
    required = {"id", "tenant_id", "package", "feature_flags", "limits"}
    missing = required - cols
    assert not missing, f"public.tenant_configs hiányzó oszlopok: {missing}"


def test_public_tenant_domains_exists(db_engine):
    assert _table_exists(db_engine, "public", "tenant_domains"), "public.tenant_domains tábla hiányzik"


def test_public_tenant_domains_structure(db_engine):
    cols = _columns(db_engine, "public", "tenant_domains")
    required = {"id", "tenant_id", "domain", "verified_at", "created_at"}
    missing = required - cols
    assert not missing, f"public.tenant_domains hiányzó oszlopok: {missing}"


# --- Demo séma és táblák ---

def test_demo_schema_exists(db_engine):
    assert _schema_exists(db_engine, "demo"), "demo séma hiányzik (futtasd: python scripts/init_db.py)"


@pytest.mark.parametrize("table", [
    "users",
    "user_invite_tokens",
    "refresh_tokens",
    "settings",
    "two_factor_codes",
    "two_factor_attempts",
    "pending_2fa_logins",
    "audit_log",
    "knowledge_bases",
])
def test_demo_table_exists(db_engine, table):
    if not _schema_exists(db_engine, "demo"):
        pytest.skip("demo séma nincs (init_db)")
    assert _table_exists(db_engine, "demo", table), f"demo.{table} tábla hiányzik"


def test_demo_users_structure(db_engine):
    if not _table_exists(db_engine, "demo", "users"):
        pytest.skip("demo.users nincs")
    cols = _columns(db_engine, "demo", "users")
    required = {"id", "email", "password_hash", "is_active", "role", "created_at"}
    missing = required - cols
    assert not missing, f"demo.users hiányzó oszlopok: {missing}"
