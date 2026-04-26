from __future__ import annotations

import importlib

__all__ = ["TenantPlatformModule", "get_module"]


def __getattr__(name: str):
    if name in ("TenantPlatformModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.tenant.module"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
