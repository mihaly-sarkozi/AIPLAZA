from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext
from core.kernel.interface.app_conventions import module_key


class LandingAppModule(BaseAppModule):
    key = module_key("landing")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return LandingAppModule()


__all__ = ["LandingAppModule", "get_module"]
