# tests/conftest.py
"""
Shared pytest fixtures. No top-level imports from config or apps so that
pytest collection does not load the full runtime stack or fail on missing config.
App and heavy deps are loaded only when a fixture that needs them is used.
Use the app fixture (from tests.app_factory) for tests that need the API; avoid
importing main.app directly in tests.
"""
import os

os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "100")
os.environ.setdefault("DISABLE_CSRF", "1")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-api-key")

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session")
def app():
    """FastAPI app for integration tests; session scope, lazy load via app_factory."""
    from tests.app_factory import create_test_app
    return create_test_app()


@pytest.fixture
def mock_user_repo(sample_user):
    """Mock user repo: get_by_id(1) → sample_user, get_owner() → sample_user; update(u) → u."""
    repo = MagicMock()
    repo.get_by_id.side_effect = lambda id: sample_user if id == 1 else None
    repo.get_owner.return_value = sample_user
    repo.update.side_effect = lambda u: u
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
def client(app, mock_login_service, mock_user_repo):
    """TestClient with login/user repo overrides and demo tenant."""
    from fastapi.testclient import TestClient

    from config.settings import settings
    from apps.core.di import get_login_service, get_user_repository
    from apps.core.container.app_container import container
    from apps.auth.domain.tenant import Tenant

    demo_tenant = Tenant(id=1, slug="demo", name="Demo", created_at=datetime.now(timezone.utc))
    app.dependency_overrides[get_login_service] = lambda: mock_login_service
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    base_url = f"http://demo.{settings.tenant_base_domain}"
    with patch.object(container.tenant_repo, "get_by_slug", return_value=demo_tenant):
        with TestClient(app, base_url=base_url) as c:
            yield c
    app.dependency_overrides.pop(get_login_service, None)
    app.dependency_overrides.pop(get_user_repository, None)


@pytest.fixture
def client_with_refresh(app, client, mock_refresh_service):
    from apps.core.di import get_refresh_service
    app.dependency_overrides[get_refresh_service] = lambda: mock_refresh_service
    yield client
    app.dependency_overrides.pop(get_refresh_service, None)


@pytest.fixture
def mock_logout_service():
    from tests.conftest import MockLogoutService
    return MockLogoutService()


@pytest.fixture
def client_authenticated(app, client, sample_user, mock_logout_service):
    from apps.core.di import get_logout_service
    from apps.core.security.auth_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_logout_service] = lambda: mock_logout_service
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_logout_service, None)


@pytest.fixture
def sample_user():
    from apps.users.domain.user import User
    return User(
        id=1,
        email="admin@example.com",
        password_hash="",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_user_service(sample_user):
    from apps.users.domain.user import User
    svc = MagicMock()
    svc.list_all.return_value = []
    svc.get_by_id.side_effect = lambda uid: sample_user if uid == 1 else None
    svc.create.side_effect = lambda **kw: User(
        id=2,
        email=kw.get("email", "new@example.com"),
        password_hash="",
        is_active=False,
        role=kw.get("role", "user"),
        created_at=datetime.now(timezone.utc),
        name=kw.get("name"),
    )
    def _update(user_id, current_user_id=0, name=None, is_active=None, email=None, role=None):
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
    from apps.core.di import get_user_service, get_logout_service
    from apps.core.security.auth_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    app.dependency_overrides[get_logout_service] = lambda: mock_logout_service
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_user_service, None)
    app.dependency_overrides.pop(get_logout_service, None)


@pytest.fixture
def mock_settings_service():
    svc = MagicMock()
    svc.is_two_factor_enabled.return_value = False
    svc.set_two_factor_enabled.side_effect = None
    return svc


@pytest.fixture
def mock_chat_service():
    svc = MagicMock()
    async def _chat(question: str):
        return f"Echo: {question}"
    svc.chat.side_effect = _chat
    return svc


# --- Mock service classes (no app imports; exceptions imported inside methods) ---


class MockLoginService:
    def __init__(self):
        self.result = None
        self.user_repository = None
        self.raise_2fa_too_many = False

    def login(self, inp):
        if self.raise_2fa_too_many and getattr(inp, "pending_token", None) and getattr(inp, "two_factor_code", None):
            from apps.auth.application.exceptions import TwoFactorTooManyAttemptsError
            raise TwoFactorTooManyAttemptsError()
        return self.result


class MockRefreshService:
    def __init__(self):
        self.result = None
        self.verify_payload = {"sub": "1", "typ": "refresh"}
        self.tokens = MagicMock()
        self.tokens.verify.side_effect = lambda rt: self.verify_payload

    def refresh(self, refresh_token: str, ip=None, ua=None, tenant_slug=None, *, correlation_id=None, **kwargs):
        return self.result


class MockLogoutService:
    def __init__(self):
        self.result = True

    def logout(self, refresh_token: str, ip=None, ua=None, *, tenant_slug=None, correlation_id=None, **kwargs):
        return self.result
