from __future__ import annotations

from apps.contracts import module_key
from core.platform.contract import AppModule, ModuleContext


class PackagesAppModule(AppModule):
    key = module_key("packages")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> AppModule:
    return PackagesAppModule()
