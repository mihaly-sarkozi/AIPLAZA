from __future__ import annotations

import importlib

__all__ = ["PlatformAdminModule", "get_module"]


def __getattr__(name: str):
    if name in ("PlatformAdminModule", "get_module"):
        return getattr(importlib.import_module("core.platform_modules.platform_admin.module"), name)
    raise AttributeError(name)

