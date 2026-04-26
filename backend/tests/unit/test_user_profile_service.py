from __future__ import annotations

from datetime import datetime, timezone

from core.capabilities.users.dto import User
from core.capabilities.users.service.profile_service import UserProfileService
from core.extensions.tenant.context.request_tenant_context import RequestTenantContext
from core.extensions.tenant.dto import TenantConfig, TenantStatus


class _UserRepo:
    def __init__(self, *, current_user: User, owner: User | None) -> None:
        self._current_user = current_user
        self._owner = owner
        self.updated_users: list[User] = []

    def get_owner(self) -> User | None:
        return self._owner

    def get_by_id(self, user_id: int) -> User | None:
        if self._current_user.id == user_id:
            return self._current_user
        if self._owner and self._owner.id == user_id:
            return self._owner
        return None

    def update(self, user: User, *, updated_by: int | None = None) -> User:
        self._current_user = user
        self.updated_users.append(user)
        return user


class _TrainingReader:
    def tenant_has_training_material(self, tenant) -> bool:
        return False


def _user(*, user_id: int, locale: str | None = None, theme: str | None = None) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        preferred_locale=locale,
        preferred_theme=theme,
    )


def _tenant_context() -> RequestTenantContext:
    return RequestTenantContext(
        tenant_id=7,
        slug="demo-tenant",
        name="Demo Tenant",
        created_at=datetime.now(timezone.utc),
        status=TenantStatus(tenant_id=7, slug="demo-tenant", is_active=True),
        config=TenantConfig(
            tenant_id=7,
            slug="demo-tenant",
            package="free",
            feature_flags={"demo_mode": True},
            limits={},
        ),
        domain=None,
        correlation_id="corr-1",
        security_version=0,
    )


def test_get_me_uses_owner_fallback_and_tenant_flags():
    current_user = _user(user_id=1, locale=None, theme=None)
    owner = _user(user_id=2, locale="en", theme="dark")
    service = UserProfileService(user_repository=_UserRepo(current_user=current_user, owner=owner))

    payload = service.get_me(user=current_user, tenant=_tenant_context(), training_status_reader=_TrainingReader())

    assert payload["locale"] == "en"
    assert payload["theme"] == "dark"
    assert payload["tenant_demo_mode"] is True
    assert payload["tenant_kb_has_training"] is False


def test_update_me_normalizes_invalid_preferences_to_none():
    current_user = _user(user_id=1, locale="hu", theme="light")
    owner = _user(user_id=2, locale="en", theme="dark")
    repo = _UserRepo(current_user=current_user, owner=owner)
    service = UserProfileService(user_repository=repo)

    payload = service.update_me(
        user=current_user,
        name="  Teszt User  ",
        preferred_locale="de",
        preferred_theme="matrix",
        updated_by=1,
    )

    assert repo.updated_users
    updated = repo.updated_users[-1]
    assert updated.name == "Teszt User"
    assert updated.preferred_locale is None
    assert updated.preferred_theme is None
    assert payload["locale"] == "en"
    assert payload["theme"] == "dark"
    assert "tenant_demo_mode" not in payload
