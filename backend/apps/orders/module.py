from __future__ import annotations

from apps.orders.bootstrap.app_module import OrdersAppModule as _OrdersAppModule
from core.kernel.interface import BaseAppModule


class OrdersAppModule(_OrdersAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return OrdersAppModule()


__all__ = ["OrdersAppModule", "get_module"]
