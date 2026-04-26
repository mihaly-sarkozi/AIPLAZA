from __future__ import annotations

import importlib

__all__ = ["DomainPlatformModule", "get_module"]


def __getattr__(name: str):
    if name in ("DomainPlatformModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.domain.module"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
