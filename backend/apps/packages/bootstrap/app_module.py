from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext
from core.kernel.interface.app_conventions import module_key


class PackagesAppModule(BaseAppModule):
    key = module_key("packages")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return PackagesAppModule()


__all__ = ["PackagesAppModule", "get_module"]
