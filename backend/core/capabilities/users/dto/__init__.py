from __future__ import annotations

import importlib

__all__ = ["InviteToken", "User"]

_LAZY: dict[str, tuple[str, str]] = {
    "InviteToken": ("core.capabilities.users.dto.invite_token", "InviteToken"),
    "User": ("core.capabilities.users.dto.user", "User"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
