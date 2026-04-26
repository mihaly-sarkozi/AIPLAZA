from __future__ import annotations

import importlib

__all__ = ["UsersPlatformModule", "get_module"]


def __getattr__(name: str):
    if name in ("UsersPlatformModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.users.module"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
