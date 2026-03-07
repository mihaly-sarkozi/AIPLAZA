# tests/conftest.py
"""Közös pytest fixture-ek: app, client, mock login/refresh/logout/user service (dependency override)."""
import os

# Login rate limit: tesztekben magasabb limit (ugyanaz az IP = testclient), különben 5/perc 429-et adna
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "100")

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from config.settings import settings
from apps.core.di import (
    get_login_service,
    get_refresh_service,
    get_logout_service,
    get_user_service,
    get_user_repository,
    get_settings_service,
    get_chat_service,
)
from apps.core.security.auth_dependencies import get_current_user
from apps.core.container.app_container import container
from apps.auth.application.dto import LoginSuccess, LoginTwoFactorRequired
from apps.users.domain.user import User
from apps.auth.domain.tenant import Tenant

# Teszt tenant: a middleware ezt várja Host: demo.local esetén (tenant_base_domain=local).
DEMO_TENANT = Tenant(id=1, slug="demo", name="Demo", created_at=datetime.now(timezone.utc))


class MockLoginService:
    """A login route csak a login(inp) visszatérését használja. Ezt állítjuk teszt szerint."""
    def __init__(self):
        self.result = None
        self.user_repository = None  # refresh route használja: get_by_id(1) → user
        self.raise_2fa_too_many = False  # True → step2-nál TwoFactorTooManyAttemptsError (429 teszt)

    def login(self, inp):
        if self.raise_2fa_too_many and getattr(inp, "pending_token", None) and getattr(inp, "two_factor_code", None):
            from apps.auth.application.exceptions import TwoFactorTooManyAttemptsError
            raise TwoFactorTooManyAttemptsError()
        return self.result


class MockRefreshService:
    """Refresh route: refresh(rt, ip, ua) → (access, new_refresh, access_jti) vagy None; tokens.verify(rt) → payload."""
    def __init__(self):
        self.result = None  # (access, new_refresh, access_jti) vagy None
        self.verify_payload = {"sub": "1", "typ": "refresh"}
        self.tokens = MagicMock()
        self.tokens.verify.side_effect = lambda rt: self.verify_payload

    def refresh(self, refresh_token: str, ip=None, ua=None, tenant_slug=None, *, correlation_id=None, **kwargs):
        return self.result


class MockLogoutService:
    """Logout route: logout(rt) → True/False."""
    def __init__(self):
        self.result = True

    def logout(self, refresh_token: str, ip=None, ua=None, *, tenant_slug=None, correlation_id=None, **kwargs):
        return self.result


@pytest.fixture
def mock_user_repo(sample_user):
    """Mock user repo: get_by_id(1) → sample_user, get_owner() → sample_user; update(u) → u; update_password, reset_failed_login no-op."""
    repo = MagicMock()
    repo.get_by_id.side_effect = lambda id: sample_user if id == 1 else None
    repo.get_owner.return_value = sample_user
    repo.update.side_effect = lambda u: u  # PATCH /auth/me
    return repo


@pytest.fixture
def mock_login_service(mock_user_repo):
    """Login mock; user_repository a refresh tesztekhez (get_by_id(1) → user)."""
    svc = MockLoginService()
    svc.user_repository = mock_user_repo
    return svc


@pytest.fixture
def mock_refresh_service():
    return MockRefreshService()


@pytest.fixture
def client(mock_login_service, mock_user_repo):
    """TestClient a /api prefix alatti végpontokhoz. LoginService + tenant + user_repo mock."""
    app.dependency_overrides[get_login_service] = lambda: mock_login_service
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    base_url = f"http://demo.{settings.tenant_base_domain}"
    with patch.object(container.tenant_repo, "get_by_slug", return_value=DEMO_TENANT):
        with TestClient(app, base_url=base_url) as c:
            yield c
    app.dependency_overrides.pop(get_login_service, None)
    app.dependency_overrides.pop(get_user_repository, None)


@pytest.fixture
def client_with_refresh(client, mock_refresh_service):
    """Client + RefreshService felülírva (refresh tesztekhez)."""
    app.dependency_overrides[get_refresh_service] = lambda: mock_refresh_service
    yield client
    app.dependency_overrides.pop(get_refresh_service, None)


@pytest.fixture
def mock_logout_service():
    return MockLogoutService()


@pytest.fixture
def client_authenticated(client, sample_user, mock_logout_service):
    """Client ahol get_current_user → sample_user (me, logout tesztekhez). Opcionálisan logout mock."""
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_logout_service] = lambda: mock_logout_service
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_logout_service, None)


@pytest.fixture
def sample_user():
    """Egy domain User a sikeres login válaszhoz (mock LoginSuccess)."""
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
    """Mock UserService: list_all, get_by_id, create, update, delete, validate_invite_token, set_password, resend_invite."""
    svc = MagicMock()
    # Alapértelmezések: list_all → üres lista, get_by_id(1) → sample_user
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
    svc.set_password.side_effect = None  # success
    svc.resend_invite.side_effect = None  # success
    return svc


@pytest.fixture
def client_superuser(client, sample_user, mock_user_service, mock_logout_service):
    """Client superuserral (get_current_user → sample_user), UserService mock (CRUD, resend, set-password)."""
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    app.dependency_overrides[get_logout_service] = lambda: mock_logout_service
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_user_service, None)
    app.dependency_overrides.pop(get_logout_service, None)


@pytest.fixture
def mock_settings_service():
    """Settings: is_two_factor_enabled, set_two_factor_enabled."""
    svc = MagicMock()
    svc.is_two_factor_enabled.return_value = False
    svc.set_two_factor_enabled.side_effect = None
    return svc


@pytest.fixture
def mock_chat_service():
    """Chat: chat(question) async → answer string."""
    svc = MagicMock()
    async def _chat(question: str):
        return f"Echo: {question}"
    svc.chat.side_effect = _chat
    return svc
