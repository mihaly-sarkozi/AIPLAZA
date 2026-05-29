from __future__ import annotations

from apps.profile.bootstrap.app_module import ProfileAppModule as _ProfileAppModule
from core.kernel.interface import BaseAppModule


class ProfileAppModule(_ProfileAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return ProfileAppModule()


__all__ = ["ProfileAppModule", "get_module"]
