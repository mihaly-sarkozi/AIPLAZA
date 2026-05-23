# backend/core/modules/auth/container/__init__.py
# Feladat: Az auth feature container lazy exportfelülete. Az AuthFeatureContainer és build_auth_feature importját késlelteti, hogy a modul assembly olcsón importálható maradjon. Auth container csomagbelépő a modulregisztráció és lifecycle state számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["AuthFeatureContainer", "build_auth_feature"]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthFeatureContainer": ("core.modules.auth.container.auth_container", "AuthFeatureContainer"),
    "build_auth_feature": ("core.modules.auth.container.auth_container", "build_auth_feature"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
