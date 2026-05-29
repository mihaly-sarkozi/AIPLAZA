from __future__ import annotations

from apps.settings.bootstrap.app_module import SettingsAppModule as _SettingsAppModule
from core.kernel.interface import BaseAppModule


class SettingsAppModule(_SettingsAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return SettingsAppModule()


__all__ = ["SettingsAppModule", "get_module"]
