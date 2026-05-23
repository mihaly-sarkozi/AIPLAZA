# backend/core/modules/brand/__init__.py
# Feladat: A brand core modul lazy exportfelülete. A BrandCoreModule osztályt csak kérésre importálja, hogy a modulok betöltése ne húzza be azonnal a brand service, repository és router függőségeket. Core platform modul belépési pont, amelyet az app manifest és a core.modules csomag használ.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["BrandCoreModule"]


def __getattr__(name: str):
    if name == "BrandCoreModule":
        return getattr(importlib.import_module("core.modules.brand.brand"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
