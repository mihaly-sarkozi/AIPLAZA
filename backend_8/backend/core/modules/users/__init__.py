# backend/core/modules/users/__init__.py
# Feladat: A users modul lazy exportfelületét adja. A UsersCoreModule-t csak kérésre importálja, hogy a csomag betöltése ne húzza be a repository, router és service rétegeket. Core platform users modul belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["UsersCoreModule"]


def __getattr__(name: str):
    if name == "UsersCoreModule":
        return getattr(importlib.import_module("core.modules.users.users"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
