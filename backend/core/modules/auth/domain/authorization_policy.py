# backend/core/modules/auth/domain/authorization_policy.py
# Feladat: Frameworkfüggetlen authorization döntési policyt ad aktív user, permission és role ellenőrzéshez. A FastAPI dependency réteg ezt használja, de maga a modul csak domain döntést ad vissza AuthorizationDecision formában. Auth domain policy, amely a PermissionService-re épül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from core.modules.users.domain.dto import User


def normalize_values(values: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        items = (values,)
    else:
        items = tuple(values)
    return tuple(str(item).strip() for item in items if str(item).strip())


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str | None = None


class AuthorizationPolicy:
    def __init__(self, permission_service) -> None:
        self._permission_service = permission_service

    def ensure_active_user(self, user: User | None) -> AuthorizationDecision:
        if user is None:
            return AuthorizationDecision(False, "missing_user")
        if not getattr(user, "is_active", False):
            return AuthorizationDecision(False, "inactive_user")
        return AuthorizationDecision(True)

    def ensure_permission(self, user: User | None, permission: str) -> AuthorizationDecision:
        active = self.ensure_active_user(user)
        if not active.allowed:
            return active
        if not self._permission_service.has_permission(user, permission):
            return AuthorizationDecision(False, f"missing_permission:{permission}")
        return AuthorizationDecision(True)

    def ensure_any_permission(self, user: User | None, permissions: str | Iterable[str]) -> AuthorizationDecision:
        normalized_permissions = normalize_values(permissions)
        active = self.ensure_active_user(user)
        if not active.allowed:
            return active
        if not normalized_permissions or not self._permission_service.has_any_permission(user, normalized_permissions):
            return AuthorizationDecision(False, f"missing_any_permission:{', '.join(normalized_permissions)}")
        return AuthorizationDecision(True)

    def ensure_all_permissions(self, user: User | None, permissions: str | Iterable[str]) -> AuthorizationDecision:
        normalized_permissions = normalize_values(permissions)
        active = self.ensure_active_user(user)
        if not active.allowed:
            return active
        if not normalized_permissions:
            return AuthorizationDecision(False, "missing_all_permissions:")
        if not all(self._permission_service.has_permission(user, permission) for permission in normalized_permissions):
            return AuthorizationDecision(False, f"missing_all_permissions:{', '.join(normalized_permissions)}")
        return AuthorizationDecision(True)

    def ensure_role(self, user: User | None, roles: str | Iterable[str]) -> AuthorizationDecision:
        normalized_roles = tuple(role.lower() for role in normalize_values(roles))
        active = self.ensure_active_user(user)
        if not active.allowed:
            return active
        user_role = (getattr(user, "role", None) or "").strip().lower()
        if not normalized_roles or user_role not in normalized_roles:
            return AuthorizationDecision(False, f"missing_role:{', '.join(normalized_roles)}")
        return AuthorizationDecision(True)
