from __future__ import annotations

import importlib

__all__ = ["AuthPlatformModule", "get_module"]


def __getattr__(name: str):
    if name in ("AuthPlatformModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.auth.module"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
