from __future__ import annotations

import importlib

__all__ = ["PermissionService", "build_default_role_permissions"]

_LAZY: dict[str, tuple[str, str]] = {
    "PermissionService": ("core.platform.permissions.permission_service", "PermissionService"),
    "build_default_role_permissions": ("core.platform.permissions.permission_service", "build_default_role_permissions"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
