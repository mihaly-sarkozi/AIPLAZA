from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext
from core.kernel.interface.app_conventions import module_key


class OrdersAppModule(BaseAppModule):
    key = module_key("orders")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return OrdersAppModule()


__all__ = ["OrdersAppModule", "get_module"]
