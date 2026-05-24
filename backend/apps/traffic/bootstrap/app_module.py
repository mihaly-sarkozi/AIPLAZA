from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext
from core.kernel.interface.app_conventions import module_key


class TrafficAppModule(BaseAppModule):
    key = module_key("traffic")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return TrafficAppModule()


__all__ = ["TrafficAppModule", "get_module"]
