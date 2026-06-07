# backend/core/kernel/security/permission_service.py
# Feladat: Platform permission registryt és role alapú permission ellenőrzést ad. A manifestből érkező ismert jogosultságokat tárolja, majd user role alapján dönti el, hogy egy aktív user megkapja-e az adott permissiont. Core authorization helper, amelyet runtime wiring épít fel és platform endpointok használhatnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass, field

from core.modules.users.domain.dto import User


def build_default_role_permissions() -> dict[str, set[str]]:
    return {
        "owner": {"*"},
        "admin": {
            "auth.login",
            "auth.refresh",
            "auth.logout",
            "users.read",
            "users.write",
            "users.invite",
            "knowledge.read",
            "kb.read",
            "kb.train",
            "settings.read",
            "settings.write",
            "domain.read",
            "domain.write",
            "billing.read",
        },
        "user": {
            "auth.login",
            "auth.refresh",
            "auth.logout",
        },
    }


@dataclass
class PermissionService:
    known_permissions: set[str] = field(default_factory=set)
    role_permissions: dict[str, set[str]] = field(default_factory=build_default_role_permissions)

    def register_permissions(self, permissions: list[str] | tuple[str, ...] | set[str]) -> None:
        self.known_permissions.update(str(permission).strip() for permission in permissions if str(permission).strip())

    def list_permissions_for_role(self, role: str | None) -> set[str]:
        normalized_role = (role or "user").strip().lower() or "user"
        granted = set(self.role_permissions.get(normalized_role, set()))
        if "*" in granted:
            return set(self.known_permissions)
        return {permission for permission in granted if permission in self.known_permissions}

    def has_role_permission(self, role: str | None, permission: str) -> bool:
        normalized_permission = (permission or "").strip()
        if not normalized_permission or normalized_permission not in self.known_permissions:
            return False
        return normalized_permission in self.list_permissions_for_role(role)

    def has_permission(self, user: User | None, permission: str) -> bool:
        if user is None or not getattr(user, "is_active", False):
            return False
        return self.has_role_permission(getattr(user, "role", None), permission)

    def has_any_permission(self, user: User | None, permissions: list[str] | tuple[str, ...] | set[str]) -> bool:
        return any(self.has_permission(user, permission) for permission in permissions)

