"""DB séma tesztek: public és demo táblák/szerkezet létezik és megfelelő."""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Backend gyökér (config, apps importok). Pytest futáskor a pythonpath miatt már eléri;
# ez a sor direkt futtatáshoz kell (pl. python backend/tests/integration/test_db_schema.py).
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# .env betöltése (backend/.env vagy repo-gyökér .env)
_env = _root / ".env"
if not _env.exists():
    _env = _root.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _ensure_demo_schema(ensure_demo_test_tenant):
    return ensure_demo_test_tenant


def _get_engine() -> Engine | None:
    try:
        from core.kernel.config.config_loader import settings
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
    required = {"id", "slug", "name", "created_at", "created_by", "updated_at", "updated_by", "security_version", "is_active"}
    missing = required - cols
    assert not missing, f"public.tenants hiányzó oszlopok: {missing}"


def test_public_tenant_configs_exists(db_engine):
    assert _table_exists(db_engine, "public", "tenant_configs"), "public.tenant_configs tábla hiányzik"


def test_public_tenant_configs_structure(db_engine):
    cols = _columns(db_engine, "public", "tenant_configs")
    required = {"id", "tenant_id", "package", "feature_flags", "limits", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"public.tenant_configs hiányzó oszlopok: {missing}"


def test_public_tenant_domains_exists(db_engine):
    assert _table_exists(db_engine, "public", "tenant_domains"), "public.tenant_domains tábla hiányzik"


def test_public_tenant_domains_structure(db_engine):
    cols = _columns(db_engine, "public", "tenant_domains")
    required = {"id", "tenant_id", "domain", "verified_at", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"public.tenant_domains hiányzó oszlopok: {missing}"


# --- Demo séma és táblák ---

def test_demo_schema_exists(db_engine):
    assert _schema_exists(db_engine, "demo"), "demo séma hiányzik (futtasd: python backend/scripts/init_db.py)"


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
    "kb_user_permission",
])
def test_demo_table_exists(db_engine, table):
    if not _schema_exists(db_engine, "demo"):
        pytest.skip("demo séma nincs (init_db)")
    assert _table_exists(db_engine, "demo", table), f"demo.{table} tábla hiányzik"


def test_demo_kb_user_permissions_structure(db_engine):
    if not _table_exists(db_engine, "demo", "kb_user_permission"):
        pytest.skip("demo.kb_user_permission nincs")
    cols = _columns(db_engine, "demo", "kb_user_permission")
    required = {"id", "kb_id", "user_id", "permission", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"demo.kb_user_permission hiányzó oszlopok: {missing}"


def test_demo_users_structure(db_engine):
    if not _table_exists(db_engine, "demo", "users"):
        pytest.skip("demo.users nincs")
    cols = _columns(db_engine, "demo", "users")
    required = {
        "id",
        "email",
        "password_hash",
        "is_active",
        "role",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "credentials_password_set",
    }
    missing = required - cols
    assert not missing, f"demo.users hiányzó oszlopok: {missing}"


def test_demo_audit_log_structure(db_engine):
    if not _table_exists(db_engine, "demo", "audit_log"):
        pytest.skip("demo.audit_log nincs")
    cols = _columns(db_engine, "demo", "audit_log")
    required = {"id", "created_at", "user_id", "action", "details", "ip", "user_agent"}
    missing = required - cols
    assert not missing, f"demo.audit_log hiányzó oszlopok: {missing}"


def test_demo_refresh_tokens_structure(db_engine):
    if not _table_exists(db_engine, "demo", "refresh_tokens"):
        pytest.skip("demo.refresh_tokens nincs")
    cols = _columns(db_engine, "demo", "refresh_tokens")
    required = {"id", "user_id", "jti", "token_hash", "valid", "expires_at", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"demo.refresh_tokens hiányzó oszlopok: {missing}"


def test_demo_settings_structure(db_engine):
    if not _table_exists(db_engine, "demo", "settings"):
        pytest.skip("demo.settings nincs")
    cols = _columns(db_engine, "demo", "settings")
    required = {"id", "key", "value", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"demo.settings hiányzó oszlopok: {missing}"


def test_demo_two_factor_codes_structure(db_engine):
    if not _table_exists(db_engine, "demo", "two_factor_codes"):
        pytest.skip("demo.two_factor_codes nincs")
    cols = _columns(db_engine, "demo", "two_factor_codes")
    required = {"id", "user_id", "code_hash", "email", "expires_at", "used", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"demo.two_factor_codes hiányzó oszlopok: {missing}"


def test_demo_two_factor_attempts_structure(db_engine):
    if not _table_exists(db_engine, "demo", "two_factor_attempts"):
        pytest.skip("demo.two_factor_attempts nincs")
    cols = _columns(db_engine, "demo", "two_factor_attempts")
    required = {"id", "scope", "scope_key", "attempts", "window_start_at", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"demo.two_factor_attempts hiányzó oszlopok: {missing}"


def test_demo_pending_2fa_logins_structure(db_engine):
    if not _table_exists(db_engine, "demo", "pending_2fa_logins"):
        pytest.skip("demo.pending_2fa_logins nincs")
    cols = _columns(db_engine, "demo", "pending_2fa_logins")
    required = {"id", "token", "user_id", "expires_at", "created_at", "created_by"}
    missing = required - cols
    assert not missing, f"demo.pending_2fa_logins hiányzó oszlopok: {missing}"


def test_demo_knowledge_bases_structure(db_engine):
    if not _table_exists(db_engine, "demo", "knowledge_bases"):
        pytest.skip("demo.knowledge_bases nincs")
    cols = _columns(db_engine, "demo", "knowledge_bases")
    required = {"id", "uuid", "name", "qdrant_collection_name", "created_at", "created_by", "updated_at", "updated_by"}
    missing = required - cols
    assert not missing, f"demo.knowledge_bases hiányzó oszlopok: {missing}"


def test_demo_user_invite_tokens_structure(db_engine):
    if not _table_exists(db_engine, "demo", "user_invite_tokens"):
        pytest.skip("demo.user_invite_tokens nincs")
    cols = _columns(db_engine, "demo", "user_invite_tokens")
    required = {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "used_at",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    }
    missing = required - cols
    assert not missing, f"demo.user_invite_tokens hiányzó oszlopok: {missing}"
