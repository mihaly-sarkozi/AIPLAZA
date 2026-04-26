from __future__ import annotations

from apps.contracts import module_key
from core.platform.contract import AppModule, ModuleContext


class TrafficAppModule(AppModule):
    key = module_key("traffic")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> AppModule:
    return TrafficAppModule()
