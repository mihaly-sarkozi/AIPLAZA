from __future__ import annotations

import importlib

__all__ = ["UserInviteTokenORM", "UserORM"]

_LAZY: dict[str, tuple[str, str]] = {
    "UserORM": ("core.capabilities.users.models.user_orm", "UserORM"),
    "UserInviteTokenORM": ("core.capabilities.users.models.user_invite_token_orm", "UserInviteTokenORM"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
