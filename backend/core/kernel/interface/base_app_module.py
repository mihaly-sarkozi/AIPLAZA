# backend/core/kernel/interface/base_app_module.py
# Feladat: A platform app modulok alaposztályát és lifecycle szerződését definiálja. A modulok ezen keresztül regisztrálnak service-eket, routereket, tenant schema hookokat, bootstrap/startup/shutdown hookokat és UI metadatát. Core public framework contract, amelyet minden backend app modul újrahasználhat.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from core.kernel.types.lifecycle_hook_types import BootstrapHook, LifecycleHook, TenantSchemaRegistrar
from core.kernel.interface.module_context import ModuleContext

if TYPE_CHECKING:
    from core.kernel.interface.routing import RouteRegistration


class BaseAppModule(ABC):
    """App modul alaposztály."""

    key: str

    @abstractmethod
    def register(self, container: ModuleContext) -> None:
        raise NotImplementedError

    def service_dependencies(self) -> tuple[str, ...]:
        return ()

    def optional_service_dependencies(self) -> tuple[str, ...]:
        return ()

    def routers(self) -> tuple["RouteRegistration", ...]:
        return ()

    def tenant_schema_hooks(self) -> tuple[TenantSchemaRegistrar, ...]:
        return ()

    def bootstrap_hooks(self) -> tuple[BootstrapHook, ...]:
        return ()

    def startup_hooks(self) -> tuple[LifecycleHook, ...]:
        return ()

    def shutdown_hooks(self) -> tuple[LifecycleHook, ...]:
        return ()

    def light_paths(self) -> tuple[str, ...]:
        return ()

    def permissions(self) -> tuple[str, ...]:
        return ()

    def ui_nav_meta(self) -> tuple[dict[str, Any], ...]:
        return ()


__all__ = ["BaseAppModule"]
