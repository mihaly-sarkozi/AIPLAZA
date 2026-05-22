# backend/core/modules/auth/__init__.py
# Feladat: Az auth core modul lazy exportfelülete. Az AuthCoreModule osztályt csak kérésre importálja, hogy a modulok betöltése ne húzza be azonnal az auth service, repository és router függőségeket. Core platform modul belépési pont, amelyet az app manifest és a core.modules csomag használ.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["AuthCoreModule"]


def __getattr__(name: str):
    if name == "AuthCoreModule":
        return getattr(importlib.import_module("core.modules.auth.auth"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
