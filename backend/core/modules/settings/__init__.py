# backend/core/modules/settings/__init__.py
# Feladat: A settings modul lazy exportfelületét adja. A SettingsCoreModule-t csak kérésre importálja, hogy a csomag betöltése ne húzza be az ORM, repository és tenant hook rétegeket. Core platform modul belépési pont a perzisztált tenant beállításokhoz.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

import importlib

__all__ = ["SettingsCoreModule"]


def __getattr__(name: str):
    if name == "SettingsCoreModule":
        return getattr(importlib.import_module("core.modules.settings.settings"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
