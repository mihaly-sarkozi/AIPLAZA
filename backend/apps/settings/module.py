from __future__ import annotations

# backend/apps/settings/module.py
# Feladat: Settings app modul publikus belépési pontja a bootstrap modul osztályának újraexportjával.
# Sárközi Mihály - 2026.05.29

from apps.settings.bootstrap.app_module import SettingsAppModule as _SettingsAppModule
from core.kernel.interface import BaseAppModule


class SettingsAppModule(_SettingsAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return SettingsAppModule()


__all__ = ["SettingsAppModule", "get_module"]
