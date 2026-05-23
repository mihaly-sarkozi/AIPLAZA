from __future__ import annotations

from core.kernel.interface.app_conventions import module_key
from core.kernel.interface import BaseAppModule, ModuleContext


class DemoAppModule(BaseAppModule):
    key = module_key("demo")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return DemoAppModule()
