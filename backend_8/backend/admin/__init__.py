# backend/admin/__init__.py
# Feladat: A backend-szintű platform admin csomag lazy exportfelülete. Az AdminCoreModule osztályt csak kérésre importálja, hogy a platform admin router, service és repository függőségi lánc ne töltődjön be feleslegesen. Platform-admin belépési pont a backend gyökér alatt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["AdminCoreModule"]


def __getattr__(name: str):
    if name == "AdminCoreModule":
        return getattr(importlib.import_module("admin.admin"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
