from __future__ import annotations

from apps.billing.bootstrap.app_module import BillingAppModule as _BillingAppModule
from core.kernel.interface import BaseAppModule


class BillingAppModule(_BillingAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return BillingAppModule()


__all__ = ["BillingAppModule", "get_module"]
