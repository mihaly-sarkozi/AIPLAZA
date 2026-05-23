# backend/core/modules/users/service/__init__.py
# Feladat: A users service csomag lazy exportfelülete. UserService, InviteService és UserProfileService osztályokat ad tovább routerek, container és tesztek számára. Users service belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["UserService", "InviteService", "UserProfileService"]

_LAZY: dict[str, tuple[str, str]] = {
    "UserService": ("core.modules.users.service.user_service", "UserService"),
    "InviteService": ("core.modules.users.service.invite_service", "InviteService"),
    "UserProfileService": ("core.modules.users.service.profile_service", "UserProfileService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
