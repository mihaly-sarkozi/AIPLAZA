from __future__ import annotations

from datetime import datetime, timezone

from core.modules.users.domain.dto import User
from core.modules.auth.domain.authorization_policy import AuthorizationPolicy


class _PermissionService:
    def has_permission(self, user: User | None, permission: str) -> bool:
        return bool(user and user.role == "admin" and permission == "users.write")

    def has_any_permission(self, user: User | None, permissions) -> bool:
        return any(self.has_permission(user, permission) for permission in permissions)


def _user(*, role: str = "user", is_active: bool = True) -> User:
    return User(
        id=1,
        email="tester@example.com",
        password_hash="hash",
        is_active=is_active,
        role=role,
        created_at=datetime.now(timezone.utc),
    )


def test_authorization_policy_rejects_inactive_user_before_permission_check():
    policy = AuthorizationPolicy(_PermissionService())

    decision = policy.ensure_permission(_user(role="admin", is_active=False), "users.write")

    assert decision.allowed is False
    assert decision.reason == "inactive_user"


def test_authorization_policy_accepts_required_permission_for_admin():
    policy = AuthorizationPolicy(_PermissionService())

    decision = policy.ensure_permission(_user(role="admin"), "users.write")

    assert decision.allowed is True
    assert decision.reason is None
