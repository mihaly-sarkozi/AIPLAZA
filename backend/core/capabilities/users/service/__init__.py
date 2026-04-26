from __future__ import annotations

import importlib

__all__ = ["UserService", "InviteService", "UserProfileService"]

_LAZY: dict[str, tuple[str, str]] = {
    "UserService": ("core.capabilities.users.service.user_service", "UserService"),
    "InviteService": ("core.capabilities.users.service.invite_service", "InviteService"),
    "UserProfileService": ("core.capabilities.users.service.profile_service", "UserProfileService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
