from __future__ import annotations

from apps.demo.bootstrap.app_module import DemoAppModule as _DemoAppModule
from core.kernel.interface import BaseAppModule


class DemoAppModule(_DemoAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return DemoAppModule()


__all__ = ["DemoAppModule", "get_module"]
