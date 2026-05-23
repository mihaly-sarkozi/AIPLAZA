import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.infrastructure.audit.service.audit_service import AuditService
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.infrastructure.audit.repositories.audit_log_repository import AuditLogRepository
from core.kernel.db.session import make_session_factory
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.users.domain.dto.user import User
from core.modules.users.repository.persistence import InviteTokenRepository, UserRepository

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
    except Exception as e:
        pytest.skip(f"DB nem elérhető: {e}")
    return engine


@pytest.fixture
def tenant_session_factory():
    from core.kernel.config.config_loader import settings

    token = current_tenant_schema.set("demo")
    try:
        yield make_session_factory(
            settings.database_url,
            pool_pre_ping=getattr(settings, "database_pool_pre_ping", True),
        )
    finally:
        current_tenant_schema.reset(token)


def _cleanup_user_related(engine: Engine, emails: list[str]) -> None:
    with engine.begin() as conn:
        for email in emails:
            user_id = conn.execute(
                text('SELECT id FROM "demo".users WHERE email = :email'),
                {"email": email},
            ).scalar_one_or_none()
            if user_id is None:
                continue
            conn.execute(text('DELETE FROM "demo".user_invite_tokens WHERE user_id = :user_id'), {"user_id": user_id})
            conn.execute(text('DELETE FROM "demo".refresh_tokens WHERE user_id = :user_id'), {"user_id": user_id})
            conn.execute(text('DELETE FROM "demo".pending_2fa_logins WHERE user_id = :user_id'), {"user_id": user_id})
            conn.execute(text('DELETE FROM "demo".two_factor_codes WHERE user_id = :user_id'), {"user_id": user_id})
            conn.execute(text('DELETE FROM "demo".audit_log WHERE user_id = :user_id'), {"user_id": user_id})
            conn.execute(text('DELETE FROM "demo".users WHERE id = :user_id'), {"user_id": user_id})


def _cleanup_user_related_by_id(engine: Engine, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM "demo".user_invite_tokens WHERE user_id = :user_id'), {"user_id": user_id})
        conn.execute(text('DELETE FROM "demo".refresh_tokens WHERE user_id = :user_id'), {"user_id": user_id})
        conn.execute(text('DELETE FROM "demo".pending_2fa_logins WHERE user_id = :user_id'), {"user_id": user_id})
        conn.execute(text('DELETE FROM "demo".two_factor_codes WHERE user_id = :user_id'), {"user_id": user_id})
        conn.execute(text('DELETE FROM "demo".audit_log WHERE user_id = :user_id'), {"user_id": user_id})
        conn.execute(text('DELETE FROM "demo".users WHERE id = :user_id'), {"user_id": user_id})


def test_user_repository_persists_update_password_and_security_version(db_engine, tenant_session_factory):
    user_repo = UserRepository(tenant_session_factory)
    email = f"user-repo-{uuid.uuid4().hex[:12]}@example.com"

    try:
        created = user_repo.create(
            User.new(
                email=email,
                password_hash="hash-1",
                role="user",
                is_active=False,
                name="Repo Test User",
            ),
            created_by=999,
        )

        fetched = user_repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.email == email

        updated = user_repo.update(
            fetched.with_updates(
                name="Updated Repo User",
                is_active=True,
                preferred_locale="hu",
                preferred_theme="light",
            ),
            updated_by=1001,
        )
        user_repo.update_password(created.id, "hash-2", updated_by=1002)
        user_repo.increment_security_version(created.id, updated_by=1003)

        assert updated.name == "Updated Repo User"
        assert updated.is_active is True

        with db_engine.connect() as conn:
            row = conn.execute(
                text(
                    'SELECT email, name, is_active, password_hash, created_by, updated_by, '
                    'preferred_locale, preferred_theme, security_version '
                    'FROM "demo".users WHERE id = :user_id'
                ),
                {"user_id": created.id},
            ).mappings().one()

        assert row["email"] == email
        assert row["name"] == "Updated Repo User"
        assert row["is_active"] is True
        assert row["password_hash"] == "hash-2"
        assert row["created_by"] == 999
        assert row["updated_by"] == 1003
        assert row["preferred_locale"] == "hu"
        assert row["preferred_theme"] == "light"
        assert row["security_version"] == 1
    finally:
        _cleanup_user_related(db_engine, [email])


def test_invite_token_repository_persists_and_invalidates_tokens(db_engine, tenant_session_factory):
    user_repo = UserRepository(tenant_session_factory)
    token_repo = InviteTokenRepository(tenant_session_factory)
    email = f"invite-repo-{uuid.uuid4().hex[:12]}@example.com"
    token_hash_1 = f"token-{uuid.uuid4().hex}"
    token_hash_2 = f"token-{uuid.uuid4().hex}"

    try:
        created = user_repo.create(
            User.new(
                email=email,
                password_hash="invite-hash",
                role="user",
                is_active=False,
                name="Invite Repo User",
            ),
            created_by=501,
        )

        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(hours=4)
        token_id_1 = token_repo.create(
            created.id,
            token_hash_1,
            expires_at,
            created_by=501,
            updated_by=501,
        )
        token_1 = token_repo.get_by_token_hash(token_hash_1)
        assert token_1 is not None
        assert token_1.id == token_id_1
        assert token_1.created_by == 501
        assert token_1.updated_by == 501
        assert token_1.used_at is None

        token_repo.mark_used(token_id_1, updated_by=777)
        used_token = token_repo.get_by_token_hash(token_hash_1)
        assert used_token is not None
        assert used_token.used_at is not None
        assert used_token.updated_by == 777

        token_id_2 = token_repo.create(
            created.id,
            token_hash_2,
            expires_at,
            created_by=888,
            updated_by=888,
        )
        token_repo.invalidate_all_for_user(created.id, updated_by=999)

        with db_engine.connect() as conn:
            rows = conn.execute(
                text(
                    'SELECT id, used_at, updated_by, created_by '
                    'FROM "demo".user_invite_tokens WHERE user_id = :user_id ORDER BY id'
                ),
                {"user_id": created.id},
            ).mappings().all()

        assert len(rows) == 2
        latest = next(row for row in rows if row["id"] == token_id_2)
        assert latest["created_by"] == 888
        assert latest["updated_by"] == 999
        assert latest["used_at"] is not None
    finally:
        _cleanup_user_related(db_engine, [email])


def test_user_repository_delete_depersonalizes_user_and_preserves_related_security_records(db_engine, tenant_session_factory):
    user_repo = UserRepository(tenant_session_factory)
    token_repo = InviteTokenRepository(tenant_session_factory)
    audit_service = AuditService(AuditLogRepository(tenant_session_factory))
    email = f"user-delete-{uuid.uuid4().hex[:12]}@example.com"
    created = None

    try:
        created = user_repo.create(
            User.new(
                email=email,
                password_hash="delete-hash",
                role="user",
                is_active=True,
                name="Delete Repo User",
            ),
            created_by=321,
        )

        from datetime import datetime, timedelta, timezone

        token_repo.create(
            created.id,
            f"token-{uuid.uuid4().hex}",
            datetime.now(timezone.utc) + timedelta(hours=4),
            created_by=321,
            updated_by=321,
        )
        with tenant_session_factory() as db:
            db.execute(
                text(
                    'INSERT INTO "demo".pending_2fa_logins (token, user_id, expires_at, created_at, created_by) '
                    'VALUES (:token, :user_id, :expires_at, NOW(), :created_by)'
                ),
                {
                    "token": f"pending-{uuid.uuid4().hex}",
                    "user_id": created.id,
                    "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
                    "created_by": 321,
                },
            )
            db.execute(
                text(
                    'INSERT INTO "demo".two_factor_codes (user_id, code_hash, email, expires_at, used, created_at, created_by, updated_at, updated_by) '
                    'VALUES (:user_id, :code_hash, :email, :expires_at, FALSE, NOW(), :created_by, NOW(), :updated_by)'
                ),
                {
                    "user_id": created.id,
                    "code_hash": f"hash-{uuid.uuid4().hex}",
                    "email": email,
                    "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
                    "created_by": 321,
                    "updated_by": 321,
                },
            )
            db.execute(
                text(
                    'INSERT INTO "demo".refresh_tokens (user_id, jti, token_hash, ip, user_agent, valid, expires_at, created_at, created_by, updated_at, updated_by) '
                    'VALUES (:user_id, :jti, :token_hash, :ip, :user_agent, TRUE, :expires_at, NOW(), :created_by, NOW(), :updated_by)'
                ),
                {
                    "user_id": created.id,
                    "jti": f"jti-{uuid.uuid4().hex}",
                    "token_hash": f"refresh-{uuid.uuid4().hex}",
                    "ip": "127.0.0.1",
                    "user_agent": "pytest-refresh-delete",
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
                    "created_by": 321,
                    "updated_by": 321,
                },
            )
            db.commit()
        audit_service.log(
            AuditLogAction.USER_UPDATED,
            user_id=created.id,
            details={"email": email},
            ip="127.0.0.1",
            user_agent="pytest-user-delete",
        )

        user_repo.delete(created.id, updated_by=654)

        assert user_repo.get_by_id(created.id) is None
        assert user_repo.get_by_email(email) is None
        assert all(user.id != created.id for user in user_repo.list_all())

        with db_engine.connect() as conn:
            row = conn.execute(
                text(
                    'SELECT id, email, name, is_active, role, deleted_at, deleted_by '
                    'FROM "demo".users WHERE id = :user_id'
                ),
                {"user_id": created.id},
            ).mappings().one()
            invite_row = conn.execute(
                text(
                    'SELECT COUNT(*) AS cnt, COUNT(used_at) AS used_cnt '
                    'FROM "demo".user_invite_tokens WHERE user_id = :user_id'
                ),
                {"user_id": created.id},
            ).mappings().one()
            pending_row = conn.execute(
                text(
                    'SELECT COUNT(*) AS cnt, COUNT(*) FILTER (WHERE expires_at <= NOW()) AS expired_cnt '
                    'FROM "demo".pending_2fa_logins WHERE user_id = :user_id'
                ),
                {"user_id": created.id},
            ).mappings().one()
            two_factor_row = conn.execute(
                text(
                    'SELECT COUNT(*) AS cnt, COUNT(*) FILTER (WHERE used = TRUE) AS used_cnt '
                    'FROM "demo".two_factor_codes WHERE user_id = :user_id'
                ),
                {"user_id": created.id},
            ).mappings().one()
            refresh_row = conn.execute(
                text(
                    'SELECT COUNT(*) AS cnt, COUNT(*) FILTER (WHERE valid = FALSE) AS invalid_cnt '
                    'FROM "demo".refresh_tokens WHERE user_id = :user_id'
                ),
                {"user_id": created.id},
            ).mappings().one()
            audit_user_id = conn.execute(
                text(
                    'SELECT user_id FROM "demo".audit_log '
                    'WHERE action = :action AND user_agent = :user_agent ORDER BY id DESC LIMIT 1'
                ),
                {
                    "action": AuditLogAction.USER_UPDATED.value,
                    "user_agent": "pytest-user-delete",
                },
            ).scalar_one_or_none()

        assert row["id"] == created.id
        assert row["email"] != email
        assert row["email"].startswith(f"deleted-user-{created.id}-")
        assert row["email"].endswith("@deleted.local")
        assert row["name"] is None
        assert row["is_active"] is False
        assert row["role"] == "user"
        assert row["deleted_at"] is not None
        assert row["deleted_by"] == 654
        assert invite_row["cnt"] == 1
        assert invite_row["used_cnt"] == 1
        assert pending_row["cnt"] == 1
        assert pending_row["expired_cnt"] == 1
        assert two_factor_row["cnt"] == 1
        assert two_factor_row["used_cnt"] == 1
        assert refresh_row["cnt"] == 1
        assert refresh_row["invalid_cnt"] == 1
        assert audit_user_id == created.id
    finally:
        if created is not None:
            _cleanup_user_related_by_id(db_engine, created.id)
