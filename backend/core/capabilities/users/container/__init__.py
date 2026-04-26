from __future__ import annotations

import importlib

__all__ = ["UsersFeatureContainer", "build_users_feature"]

_LAZY: dict[str, tuple[str, str]] = {
    "UsersFeatureContainer": ("core.capabilities.users.container.users_container", "UsersFeatureContainer"),
    "build_users_feature": ("core.capabilities.users.container.users_container", "build_users_feature"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
