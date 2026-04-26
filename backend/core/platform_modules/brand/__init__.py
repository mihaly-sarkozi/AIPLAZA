from __future__ import annotations

import importlib

__all__ = ["BrandPlatformModule", "get_module"]


def __getattr__(name: str):
    if name in ("BrandPlatformModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.brand.module"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
