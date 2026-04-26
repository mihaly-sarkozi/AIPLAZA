from __future__ import annotations

import importlib

__all__ = ["LifecyclePlatformModule", "get_module"]


def __getattr__(name: str):
    if name in ("LifecyclePlatformModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.lifecycle.module"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
