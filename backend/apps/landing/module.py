from __future__ import annotations

from apps.landing.bootstrap.app_module import LandingAppModule as _LandingAppModule
from core.kernel.interface import BaseAppModule


class LandingAppModule(_LandingAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return LandingAppModule()


__all__ = ["LandingAppModule", "get_module"]
