"""Platform contract public API.

Only the stable platform module/routing/lifecycle primitives are exported here.
Keep imports from this package cheap and runtime-free.
"""
from __future__ import annotations

from core.platform.contract.lifecycle import BootstrapHook, LifecycleHook, TenantSchemaRegistrar
from core.platform.contract.modules import AppModule, ModuleContext
from core.platform.contract.routing import RouteRegistration

__all__ = [
    "AppModule",
    "BootstrapHook",
    "LifecycleHook",
    "ModuleContext",
    "RouteRegistration",
    "TenantSchemaRegistrar",
]
