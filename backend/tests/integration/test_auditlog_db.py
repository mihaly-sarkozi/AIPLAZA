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
from core.modules.users.repository.persistence.user_repository import UserRepository

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


def _cleanup_user_and_audit(engine: Engine, email: str, action: str) -> None:
    with engine.begin() as conn:
        user_id = conn.execute(
            text('SELECT id FROM "demo".users WHERE email = :email'),
            {"email": email},
        ).scalar_one_or_none()
        if user_id is not None:
            conn.execute(
                text('DELETE FROM "demo".audit_log WHERE user_id = :user_id AND action = :action'),
                {"user_id": user_id, "action": action},
            )
            conn.execute(
                text('DELETE FROM "demo".users WHERE id = :user_id'),
                {"user_id": user_id},
            )


def test_audit_repository_persists_row_to_demo_schema(db_engine, tenant_session_factory):
    repo = AuditLogRepository(tenant_session_factory)
    action = AuditLogAction.USER_CREATED
    email = f"audit-repo-{uuid.uuid4().hex[:12]}@example.com"
    user_repo = UserRepository(tenant_session_factory)
    user = user_repo.create(
        User.new(
            email=email,
            password_hash="x",
            role="user",
            is_active=True,
            name="Audit Repo Test",
        )
    )

    try:
        repo.append(
            action=action,
            user_id=user.id,
            details={"email": email},
            ip="127.0.0.1",
            user_agent="pytest-audit-repo",
        )

        with db_engine.connect() as conn:
            row = conn.execute(
                text(
                    'SELECT user_id, action, details, ip, user_agent '
                    'FROM "demo".audit_log '
                    'WHERE user_id = :user_id AND action = :action '
                    'ORDER BY id DESC LIMIT 1'
                ),
                {"user_id": user.id, "action": action.value},
            ).mappings().first()

        assert row is not None
        assert row["user_id"] == user.id
        assert row["action"] == action.value
        assert '"email"' in (row["details"] or "")
        assert row["ip"] == "127.0.0.1"
        assert row["user_agent"] == "pytest-audit-repo"
    finally:
        _cleanup_user_and_audit(db_engine, email, action.value)


def test_transaction_commit_persists_business_change_and_audit(db_engine, tenant_session_factory):
    user_repo = UserRepository(tenant_session_factory)
    audit_service = AuditService(AuditLogRepository(tenant_session_factory))
    action = AuditLogAction.USER_CREATED
    email = f"audit-commit-{uuid.uuid4().hex[:12]}@example.com"

    try:
        with tenant_session_factory.transaction():
            created = user_repo.create(
                User.new(
                    email=email,
                    password_hash="x",
                    role="user",
                    is_active=True,
                    name="Txn Commit Test",
                )
            )
            audit_service.log(
                action,
                user_id=created.id,
                details={"email": email},
                ip="10.0.0.1",
                user_agent="pytest-txn-commit",
            )

        with db_engine.connect() as conn:
            user_id = conn.execute(
                text('SELECT id FROM "demo".users WHERE email = :email'),
                {"email": email},
            ).scalar_one_or_none()
            audit_count = conn.execute(
                text('SELECT COUNT(*) FROM "demo".audit_log WHERE action = :action AND user_id = :user_id'),
                {"action": action.value, "user_id": user_id},
            ).scalar_one()

        assert user_id is not None
        assert audit_count == 1
    finally:
        _cleanup_user_and_audit(db_engine, email, action.value)


def test_transaction_rollback_removes_business_change_and_audit(db_engine, tenant_session_factory):
    user_repo = UserRepository(tenant_session_factory)
    audit_service = AuditService(AuditLogRepository(tenant_session_factory))
    action = AuditLogAction.USER_CREATED
    email = f"audit-rollback-{uuid.uuid4().hex[:12]}@example.com"
    user_agent = f"pytest-txn-rollback-{uuid.uuid4().hex[:8]}"

    with pytest.raises(RuntimeError):
        with tenant_session_factory.transaction():
            created = user_repo.create(
                User.new(
                    email=email,
                    password_hash="x",
                    role="user",
                    is_active=True,
                    name="Txn Rollback Test",
                )
            )
            audit_service.log(
                action,
                user_id=created.id,
                details={"email": email},
                ip="10.0.0.2",
                user_agent=user_agent,
            )
            raise RuntimeError("force rollback")

    with db_engine.connect() as conn:
        user_id = conn.execute(
            text('SELECT id FROM "demo".users WHERE email = :email'),
            {"email": email},
        ).scalar_one_or_none()
        audit_count = conn.execute(
            text(
                'SELECT COUNT(*) FROM "demo".audit_log '
                'WHERE action = :action AND user_agent = :user_agent'
            ),
            {"action": action.value, "user_agent": user_agent},
        ).scalar_one()

    assert user_id is None
    assert audit_count == 0


def test_audit_repository_persists_null_user_and_null_details(db_engine, tenant_session_factory):
    repo = AuditLogRepository(tenant_session_factory)
    marker = f"pytest-audit-null-{uuid.uuid4().hex[:8]}"

    try:
        repo.append(
            action=AuditLogAction.LOGIN_FAILED,
            user_id=None,
            details=None,
            ip=None,
            user_agent=marker,
        )

        with db_engine.connect() as conn:
            row = conn.execute(
                text(
                    'SELECT user_id, details, ip, user_agent '
                    'FROM "demo".audit_log '
                    'WHERE action = :action AND user_agent = :user_agent '
                    'ORDER BY id DESC LIMIT 1'
                ),
                {"action": AuditLogAction.LOGIN_FAILED.value, "user_agent": marker},
            ).mappings().first()

        assert row is not None
        assert row["user_id"] is None
        assert row["details"] is None
        assert row["ip"] is None
        assert row["user_agent"] == marker
    finally:
        with db_engine.begin() as conn:
            conn.execute(
                text('DELETE FROM "demo".audit_log WHERE action = :action AND user_agent = :user_agent'),
                {"action": AuditLogAction.LOGIN_FAILED.value, "user_agent": marker},
            )
