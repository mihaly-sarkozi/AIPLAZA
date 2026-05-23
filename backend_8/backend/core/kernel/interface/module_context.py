# backend/core/kernel/interface/module_context.py
# Feladat: A BaseAppModule.register() metódusnak átadott DI és state contextet definiálja. Service, repository és factory regisztrációt, lookupot, platform service elérést és modulok közti stabil átadási pontokat biztosít. Core public framework contract, amely a bootstrap modulregisztráció és az app modulok közötti határt adja.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core.kernel.interface.keys import ServiceKey


@dataclass
class ModuleContext:
    """DI konténer, amelyet a BaseAppModule.register() kap.

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
    service_publisher: Callable[[str, Any], None] | None = None
    repository_publisher: Callable[[str, Any], None] | None = None
    factory_publisher: Callable[[str, Callable[..., Any]], None] | None = None

    @property
    def clock(self) -> Any:
        """Platform clock (SystemClock implementáció)."""
        from core.kernel.interface.keys import PLATFORM_CLOCK_SERVICE
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
        key = str(name)
        self.services[key] = instance
        if self._should_publish_to_kernel(key) and self.service_publisher is not None:
            self.service_publisher(key, instance)

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
        key = str(name)
        self.repositories[key] = instance
        if self._should_publish_to_kernel(key) and self.repository_publisher is not None:
            self.repository_publisher(key, instance)

    def get_repository(self, name: str | ServiceKey) -> Any:
        if str(name) not in self.repositories:
            raise RuntimeError(f"Repository nincs regisztrálva: {name!r}.")
        return self.repositories[str(name)]

    def register_factory(self, name: str | ServiceKey, factory: Callable[..., Any]) -> None:
        key = str(name)
        self.factories[key] = factory
        if self._should_publish_to_kernel(key) and self.factory_publisher is not None:
            self.factory_publisher(key, factory)

    def get_factory(self, name: str | ServiceKey) -> Callable[..., Any]:
        if str(name) not in self.factories:
            raise RuntimeError(f"Factory nincs regisztrálva: {name!r}.")
        return self.factories[str(name)]

    def set_state(self, name: str, value: Any) -> None:
        self.state[name] = value

    def get_state(self, name: str, default: Any = None) -> Any:
        return self.state.get(name, default)


__all__ = ["ModuleContext"]
