from __future__ import annotations

from apps.traffic.bootstrap.app_module import TrafficAppModule as _TrafficAppModule
from core.kernel.interface import BaseAppModule


class TrafficAppModule(_TrafficAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return TrafficAppModule()


__all__ = ["TrafficAppModule", "get_module"]
