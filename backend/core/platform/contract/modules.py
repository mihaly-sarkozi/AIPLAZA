"""Platform module contract.

This module defines the canonical AppModule and ModuleContext types and keeps
imports light. It does not depend on platform runtime or manifest code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from core.platform.contract.keys import ServiceKey
from core.platform.contract.lifecycle import LifecycleHook, TenantSchemaRegistrar

if TYPE_CHECKING:
    from core.platform.contract.routing import RouteRegistration


@dataclass
class ModuleContext:
    """DI konténer, amelyet az AppModule.register() kap.

    Typed property-k (platform service-ek)
    ---------------------------------------
    Ezeket használd raw string lookup helyett:

        ctx.clock                 → platform clock (SystemClock)
        ctx.session_factory       → DB session factory
        ctx.user_repository       → User repository
        ctx.tenant_repository     → Tenant repository
        ctx.email_service         → Email service (proxy)
        ctx.security_audit        → Audit service (proxy)

    DI regisztrálás
    ---------------
        ctx.register_service(APP_MY_SERVICE, service)    # saját service
        ctx.register_repository(APP_MY_REPO, repo)       # saját repo
        ctx.register_factory(APP_MY_FACTORY, factory)    # saját factory

    Platform service lekérdezés
    ---------------------------
        svc = ctx.get_platform_service(PLATFORM_SETTINGS)   # kötelező platform service
        svc = ctx.get_optional_service(PLATFORM_TENANT_USAGE)    # opcionális platform service

    BELSŐ mezők (ne használd közvetlenül app-modulokban)
    -------------------------------------------------------
        ctx.infrastructure.*   – DB, repo-k, email infra (belső részlet)
        ctx.security.*         – token, audit, event channel (belső részlet)
    """

    infrastructure: Any
    security: Any
    audit_service: Any

    services: dict[str, Any] = field(default_factory=dict)
    repositories: dict[str, Any] = field(default_factory=dict)
    factories: dict[str, Callable[..., Any]] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def clock(self) -> Any:
        """Platform clock (SystemClock implementáció)."""
        from core.platform.service_keys import PLATFORM_CLOCK_SERVICE
        return self.get_service(PLATFORM_CLOCK_SERVICE)

    @property
    def session_factory(self) -> Any:
        return self.infrastructure.db_session_factory

    @property
    def user_repository(self) -> Any:
        return self.infrastructure.repositories.user_repo

    @property
    def tenant_repository(self) -> Any:
        return self.infrastructure.repositories.tenant_repo

    @property
    def email_service(self) -> Any:
        return self.security.email_service

    @property
    def security_audit(self) -> Any:
        return self.security.audit_service

    @staticmethod
    def _should_publish_to_kernel(name: str) -> bool:
        return str(name or "").startswith("platform.")

    def get_platform_service(self, key: str | ServiceKey) -> Any:
        k = str(key)
        if k not in self.services:
            raise RuntimeError(
                f"Platform service nincs regisztrálva: {k!r}. "
                "Ellenőrizd, hogy a szükséges platform modul a service_dependencies()-ben "
                "szerepel és a regisztrációs sorrendben megelőzi ezt a modult."
            )
        return self.services[k]

    def get_optional_service(self, key: str | ServiceKey, default: Any = None) -> Any:
        return self.services.get(str(key), default)

    def register_service(self, name: str | ServiceKey, instance: Any) -> None:
        self.services[str(name)] = instance
        if self._should_publish_to_kernel(str(name)):
            from core.di import register_service as register_kernel_service
            register_kernel_service(str(name), instance)

    def get_service(self, name: str | ServiceKey) -> Any:
        if str(name) not in self.services:
            raise RuntimeError(
                f"Service nincs regisztrálva: {name!r}. "
                "Sorrendellenőrzés: kötelező dependenciákat service_dependencies()-ben kell deklarálni."
            )
        return self.services[str(name)]

    def has_service(self, name: str | ServiceKey) -> bool:
        return str(name) in self.services

    def register_repository(self, name: str | ServiceKey, instance: Any) -> None:
        self.repositories[str(name)] = instance
        if self._should_publish_to_kernel(str(name)):
            from core.di import register_repository as register_kernel_repository
            register_kernel_repository(str(name), instance)

    def get_repository(self, name: str | ServiceKey) -> Any:
        if str(name) not in self.repositories:
            raise RuntimeError(f"Repository nincs regisztrálva: {name!r}.")
        return self.repositories[str(name)]

    def register_factory(self, name: str | ServiceKey, factory: Callable[..., Any]) -> None:
        self.factories[str(name)] = factory
        if self._should_publish_to_kernel(str(name)):
            from core.di import register_factory as register_kernel_factory
            register_kernel_factory(str(name), factory)

    def get_factory(self, name: str | ServiceKey) -> Callable[..., Any]:
        if str(name) not in self.factories:
            raise RuntimeError(f"Factory nincs regisztrálva: {name!r}.")
        return self.factories[str(name)]

    def set_state(self, name: str, value: Any) -> None:
        self.state[name] = value

    def get_state(self, name: str, default: Any = None) -> Any:
        return self.state.get(name, default)


class AppModule(ABC):
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


__all__ = ["AppModule", "ModuleContext"]
