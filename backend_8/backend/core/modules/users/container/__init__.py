# backend/core/modules/users/container/__init__.py
# Feladat: A users container csomag lazy exportfelülete. A UsersFeatureContainer-t és build_users_feature factoryt adja tovább a module assembly számára. Vékony users composition belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["UsersFeatureContainer", "build_users_feature"]

_LAZY: dict[str, tuple[str, str]] = {
    "UsersFeatureContainer": ("core.modules.users.container.users_container", "UsersFeatureContainer"),
    "build_users_feature": ("core.modules.users.container.users_container", "build_users_feature"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
