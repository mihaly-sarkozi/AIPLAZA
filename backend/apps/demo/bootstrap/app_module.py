from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext
from core.kernel.interface.app_conventions import module_key


class DemoAppModule(BaseAppModule):
    key = module_key("demo")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return DemoAppModule()


__all__ = ["DemoAppModule", "get_module"]
