"""Integration / HTTP / DB fixture-ök – csak ``tests/integration`` gyűjtésnél töltődnek be."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import MockLoginService, MockLogoutService, MockRefreshService


@pytest.fixture(scope="session")
def ensure_demo_test_tenant():
    """DB-s integration tesztekhez létrehozza a demo tenant sort és sémát."""
    try:
        from sqlalchemy import create_engine, text

        from apps.registry import load_app_modules
        from core.kernel.config.config_loader import settings
        from core.kernel.app.app_manifest import AppManifest

        from core.modules.tenant.service.tenant_schema_service import (
            create_tenant_schema,
            register_manifest_tenant_schema_hooks,
            upgrade_public_schema,
        )
    except Exception as exc:
        pytest.skip(f"Demo teszt-tenant bootstrap nem elérhető: {exc}")

    try:
        engine = create_engine(settings.database_url, future=True)
        if engine.dialect.name == "sqlite":
            pytest.skip("DB-s integration tenant bootstrap PostgreSQL-kompatibilis engine-t igényel.")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"DB nem elérhető demo teszt-tenant bootstraphoz: {exc}")

    register_manifest_tenant_schema_hooks(
        AppManifest.init_app().add_modules(
            load_app_modules(),
        )
    )
    upgrade_public_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.tenants (slug, name, security_version, is_active)
                VALUES (:slug, :name, 0, TRUE)
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {"slug": "demo", "name": "Demo"},
        )
    create_tenant_schema(engine, "demo")
    return "demo"


@pytest.fixture(scope="session")
def app():
    """FastAPI app for integration tests; session scope, lazy load via app_factory."""
    from tests.app_factory import create_test_app

    return create_test_app()


@pytest.fixture
def sample_user():
    from core.modules.users.domain.dto import User

    return User(
        id=1,
        email="admin@example.com",
        password_hash="",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_user_repo(sample_user):
    """Mock user repo: get_by_id(1) → sample_user, get_owner() → sample_user; update(u) → u."""
    repo = MagicMock()
    repo.get_by_id.side_effect = lambda id: sample_user if id == 1 else None
    repo.get_owner.return_value = sample_user
    repo.update.side_effect = lambda u, **kwargs: u
    return repo


@pytest.fixture
def mock_login_service(mock_user_repo):
    """Login mock; user_repository for refresh tests (get_by_id(1) → user)."""
    svc = MockLoginService()
    svc.user_repository = mock_user_repo
    return svc


@pytest.fixture
def mock_refresh_service():
    return MockRefreshService()


@pytest.fixture
def client(app, mock_login_service, mock_user_repo, ensure_demo_test_tenant):
    """TestClient with login/user repo overrides and demo tenant."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from core.kernel.config.config_loader import settings
    from core.kernel.deps.facade import get_login_service, get_user_repository
    from core.kernel.app.app_container import container
    from core.modules.tenant.dto import Tenant, TenantConfig, TenantDomainInfo, TenantSnapshot, TenantStatus

    tenant_id = 1
    try:
        engine = create_engine(settings.database_url, future=True)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM public.tenants WHERE slug = :slug LIMIT 1"),
                {"slug": "demo"},
            ).first()
            if row is not None:
                tenant_id = int(row[0])
    except Exception:
        pass

    demo_tenant = Tenant(id=tenant_id, slug="demo", name="Demo", created_at=datetime.now(timezone.utc))
    demo_tenant_status = TenantStatus(tenant_id=tenant_id, slug="demo", is_active=True)
    demo_tenant_config = TenantConfig(
        tenant_id=tenant_id,
        slug="demo",
        package="test",
        feature_flags={},
        limits={},
    )
    demo_snapshot = TenantSnapshot(
        tenant_id=tenant_id,
        slug="demo",
        name="Demo",
        created_at=demo_tenant.created_at,
        security_version=0,
        status=demo_tenant_status,
        config=demo_tenant_config,
        domain=TenantDomainInfo(
            request_host=f"demo.{settings.tenant_base_domain}",
            resolved_host=f"demo.{settings.tenant_base_domain}",
            is_custom_domain=False,
            verified_at=None,
        ),
    )
    app.dependency_overrides[get_login_service] = lambda: mock_login_service
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    base_url = f"http://demo.{settings.tenant_base_domain}"
    with ExitStack() as stack:
        tenant_repo = container.get_tenant_repository()
        stack.enter_context(patch.object(tenant_repo, "get_by_slug", return_value=demo_tenant))
        stack.enter_context(patch.object(tenant_repo, "get_by_domain", return_value=demo_tenant))
        stack.enter_context(patch.object(tenant_repo, "get_snapshot_by_slug", return_value=demo_snapshot))
        stack.enter_context(patch.object(tenant_repo, "get_tenant_status", return_value=demo_tenant_status))
        stack.enter_context(patch.object(tenant_repo, "get_tenant_config", return_value=demo_tenant_config))
        stack.enter_context(patch.object(tenant_repo, "get_domain", return_value=None))
        with TestClient(app, base_url=base_url) as c:
            yield c
    app.dependency_overrides.pop(get_login_service, None)
    app.dependency_overrides.pop(get_user_repository, None)


@pytest.fixture
def client_with_refresh(app, client, mock_refresh_service):
    from core.kernel.deps.facade import get_refresh_service

    app.dependency_overrides[get_refresh_service] = lambda: mock_refresh_service
    yield client
    app.dependency_overrides.pop(get_refresh_service, None)


@pytest.fixture
def mock_logout_service():
    return MockLogoutService()


@pytest.fixture
def allow_chat_usage():
    from core.kernel.deps.facade import get_service, register_service
    from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE

    previous_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    usage_service = MagicMock()
    usage_service.can_consume_question.return_value = (True, None)
    usage_service.record_question.return_value = None
    register_service(PLATFORM_TENANT_USAGE_SERVICE, usage_service)
    try:
        yield usage_service
    finally:
        register_service(PLATFORM_TENANT_USAGE_SERVICE, previous_service)


@pytest.fixture
def client_authenticated(app, client, sample_user, mock_logout_service, mock_user_repo):
    from core.modules.users.dependencies import get_user_profile_service
    from core.modules.users.service.profile_service import UserProfileService
    from core.kernel.deps.facade import get_logout_service
    from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_logout_service] = lambda: mock_logout_service
    app.dependency_overrides[get_user_profile_service] = lambda: UserProfileService(mock_user_repo)
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_logout_service, None)
    app.dependency_overrides.pop(get_user_profile_service, None)


@pytest.fixture
def mock_user_service(sample_user):
    from core.modules.users.domain.dto import User

    svc = MagicMock()
    svc.list_all.return_value = []
    svc.get_by_id.side_effect = lambda uid: sample_user if uid == 1 else None
    svc.create.side_effect = lambda **kw: User(
        id=2,
        email=kw.get("email", "new@example.com"),
        password_hash="",
        is_active=True,
        role=kw.get("role", "user"),
        created_at=datetime.now(timezone.utc),
        name=kw.get("name"),
        credentials_password_set=False,
    )

    def _update(user_id, current_user_id=0, name=None, is_active=None, email=None, role=None, **_kwargs):
        return User(
            id=user_id,
            email=email or "updated@example.com",
            password_hash="",
            is_active=is_active if is_active is not None else True,
            role=role or "user",
            created_at=datetime.now(timezone.utc),
            name=name or "Updated",
        )

    svc.update.side_effect = _update
    svc.validate_invite_token.return_value = "invalid"
    svc.set_password.side_effect = None
    svc.resend_invite.side_effect = None
    return svc


@pytest.fixture
def client_superuser(app, client, sample_user, mock_user_service, mock_logout_service):
    from core.modules.users.dependencies import get_invite_service, get_user_service
    from core.kernel.deps.facade import get_logout_service, get_service, register_service
    from core.modules.auth.web.dependencies.auth_dependencies import get_current_user
    from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE

    previous_usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    usage_service = MagicMock()
    usage_service.can_create_user.return_value = (True, None)
    register_service(PLATFORM_TENANT_USAGE_SERVICE, usage_service)
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    app.dependency_overrides[get_invite_service] = lambda: mock_user_service
    app.dependency_overrides[get_logout_service] = lambda: mock_logout_service
    yield client
    register_service(PLATFORM_TENANT_USAGE_SERVICE, previous_usage_service)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_user_service, None)
    app.dependency_overrides.pop(get_invite_service, None)
    app.dependency_overrides.pop(get_logout_service, None)


@pytest.fixture
def mock_settings_service():
    svc = MagicMock()
    svc.get_settings.return_value = {
        "two_factor_enabled": False,
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "time_format": "HH:mm",
        "billing_customer_type": "company",
        "billing_full_name": "",
        "billing_company_name": "",
        "billing_tax_id": "",
        "billing_address_line": "",
        "billing_postal_code": "",
        "billing_city": "",
        "billing_region": "",
        "billing_country": "",
    }
    svc.get_two_factor_settings.return_value = {"two_factor_enabled": False}
    svc.get_locale_settings.return_value = {
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "time_format": "HH:mm",
    }
    svc.get_billing_settings.return_value = {
        "billing_customer_type": "company",
        "billing_full_name": "",
        "billing_company_name": "",
        "billing_tax_id": "",
        "billing_address_line": "",
        "billing_postal_code": "",
        "billing_city": "",
        "billing_region": "",
        "billing_country": "",
    }
    svc.update_settings.return_value = {
        "two_factor_enabled": True,
        "timezone": "Europe/Budapest",
        "date_format": "DD.MM.YYYY",
        "time_format": "HH:mm:ss",
        "billing_customer_type": "company",
        "billing_full_name": "",
        "billing_company_name": "",
        "billing_tax_id": "",
        "billing_address_line": "",
        "billing_postal_code": "",
        "billing_city": "",
        "billing_region": "",
        "billing_country": "",
    }
    svc.update_two_factor_settings.return_value = {"two_factor_enabled": True}
    svc.update_locale_settings.return_value = {
        "timezone": "Europe/Budapest",
        "date_format": "DD.MM.YYYY",
        "time_format": "HH:mm:ss",
    }
    svc.update_billing_settings.return_value = {
        "billing_customer_type": "company",
        "billing_full_name": "",
        "billing_company_name": "Example Kft.",
        "billing_tax_id": "HU12345678",
        "billing_address_line": "Fo utca 1.",
        "billing_postal_code": "1051",
        "billing_city": "Budapest",
        "billing_region": "",
        "billing_country": "HU",
    }
    return svc


@pytest.fixture
def mock_chat_service():
    svc = MagicMock()

    async def _chat(question: str):
        return f"Echo: {question}"

    svc.chat.side_effect = _chat
    return svc
