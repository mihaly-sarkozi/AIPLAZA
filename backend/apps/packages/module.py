from __future__ import annotations

from apps.packages.bootstrap.app_module import PackagesAppModule as _PackagesAppModule
from core.kernel.interface import BaseAppModule


class PackagesAppModule(_PackagesAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return PackagesAppModule()


__all__ = ["PackagesAppModule", "get_module"]
