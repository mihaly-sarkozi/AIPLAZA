from __future__ import annotations

from apps.contracts import module_key
from core.platform.contract import AppModule, ModuleContext


class LandingAppModule(AppModule):
    key = module_key("landing")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> AppModule:
    return LandingAppModule()
