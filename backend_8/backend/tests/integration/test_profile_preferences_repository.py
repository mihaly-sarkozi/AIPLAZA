from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from apps.profile.infra.preferences_repository import ProfilePreferencesRepository

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

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
    engine = _get_engine()
    if engine is None:
        pytest.skip("Nincs database_url (PostgreSQL)")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"DB nem elérhető: {exc}")
    return engine


def _cleanup_preferences(engine: Engine, *, schema: str, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f'DELETE FROM "{schema}".profile_preferences WHERE user_id = :user_id'),
            {"user_id": user_id},
        )


def test_repository_upsert_inserts_and_reads_back_preferences(db_engine: Engine) -> None:
    repository = ProfilePreferencesRepository(db_engine)
    user_id = 700_000 + int(uuid.uuid4().hex[:6], 16)

    try:
        prefs = repository.upsert_for_user(
            tenant_slug="demo",
            user_id=user_id,
            dashboard_layout="compact",
            show_tips=False,
        )
        loaded = repository.get_for_user(tenant_slug="demo", user_id=user_id)

        assert prefs.user_id == user_id
        assert loaded.user_id == user_id
        assert loaded.dashboard_layout == "compact"
        assert loaded.show_tips is False

        with db_engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT dashboard_layout, show_tips
                    FROM "demo".profile_preferences
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            ).first()
        assert row is not None
        assert row[0] == "compact"
        assert row[1] is False
    finally:
        _cleanup_preferences(db_engine, schema="demo", user_id=user_id)


def test_repository_rejects_invalid_tenant_slug(db_engine: Engine) -> None:
    repository = ProfilePreferencesRepository(db_engine)

    with pytest.raises(ValueError, match="invalid tenant schema"):
        repository.get_for_user(tenant_slug="demo-invalid", user_id=1)
