from __future__ import annotations

import importlib

__all__ = ["AuthFeatureContainer", "build_auth_feature"]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthFeatureContainer": ("core.capabilities.auth.container.auth_container", "AuthFeatureContainer"),
    "build_auth_feature": ("core.capabilities.auth.container.auth_container", "build_auth_feature"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
