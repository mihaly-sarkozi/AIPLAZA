"""Platform manifest – a modul-összetétel leírója.

Sorrend-invariáns
=================
A rendszer MINDIG a következő sorrendben épül fel és regisztrál:

  1. Kernel inicializálás (DB, security, infrastructure)
  2. Platform modulok regisztrációja (platform_modules)  ← Phase 1
  3. Alkalmazás modulok regisztrációja (app_modules)     ← Phase 2

Ez az invariáns a ``PlatformManifest.platform_modules`` és ``app_modules``
mezők elkülönítésével van kényszerítve, és a ``register_manifest_modules()``
(bootstrap/modules.py) kétfázisú regisztrációval hajtja végre.

Tilos: platform modul az app_modules listában, vagy app modul a platform_modules listában.

Típusok
=======
  PlatformManifest  – a teljes, merged manifest amit a runtime kap
  AppManifest       – az alkalmazásréteg deklarációja (csak app_modules)
  RouteRegistration – HTTP router regisztrációs leíró
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.platform.contract.lifecycle import BootstrapHook, LifecycleHook, TenantSchemaRegistrar
from core.platform.contract.modules import AppModule
from core.platform.contract.routing import RouteRegistration

if TYPE_CHECKING:
    from fastapi import FastAPI
else:
    FastAPI = Any

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformManifest:
    """A teljes, összerakott manifest amit a runtime kap.

    platform_modules és app_modules ELKÜLÖNÍTETT listák:
      - platform_modules: core/platform_modules/* (Phase 1)
      - app_modules:      application modules (Phase 2)

    A ``modules`` property a platform + app sorrendet adja vissza,
    ami megegyezik a regisztrációs sorrenddel.
    """
    app_name: str
    description: str = ""
    version: str = "1.0"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    bootstrap_hooks: tuple[BootstrapHook, ...] = ()
    platform_modules: tuple[AppModule, ...] = ()
    app_modules: tuple[AppModule, ...] = ()
    routers: tuple[RouteRegistration, ...] = ()
    startup_hooks: tuple[LifecycleHook, ...] = ()
    shutdown_hooks: tuple[LifecycleHook, ...] = ()
    light_paths: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    tenant_schema_hooks: tuple[TenantSchemaRegistrar, ...] = ()
    ui_nav_meta: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def modules(self) -> tuple[AppModule, ...]:
        """Platform + app modulok a regisztrációs sorrendben (platform előbb)."""
        return self.platform_modules + self.app_modules


@dataclass(frozen=True)
class AppManifest:
    """Az alkalmazásréteg modul-deklarációja.

    Csak app_modules-t tartalmaz. A platform_modules a core/platform/registry.py-ban
    van definiálva, és az AppContainer tölti be automatikusan.

    Ez a struktúra a composition root és a platform között a határfelület –
    az alkalmazásréteg csak ezt adja vissza, nem PlatformManifest-et.
    """
    app_name: str | None = None
    description: str | None = None
    version: str | None = None
    app_modules: tuple[AppModule, ...] = ()
    startup_hooks: tuple[LifecycleHook, ...] = ()
    shutdown_hooks: tuple[LifecycleHook, ...] = ()
    bootstrap_hooks: tuple[BootstrapHook, ...] = ()


def build_platform_manifest(
    *,
    app_name: str,
    description: str = "",
    version: str = "1.0",
    docs_url: str | None = "/docs",
    redoc_url: str | None = "/redoc",
    platform_modules: tuple[AppModule, ...] = (),
) -> PlatformManifest:
    """Platform manifest létrehozása (platform modulok listájával, app modulok nélkül).

    Ezt a load_core_platform_manifest() hívja – az eredmény kizárólag
    platform_modules-t tartalmaz. Az app_modules üres marad, azokat a
    merge_app_manifest() adja hozzá.
    """
    return PlatformManifest(
        app_name=app_name,
        description=description,
        version=version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        platform_modules=platform_modules,
    )


def merge_app_manifest(platform_manifest: PlatformManifest, app_manifest: AppManifest) -> PlatformManifest:
    """Platform és app manifest összefésülése a végleges PlatformManifest-be.

    Sorrend-invariáns érvényesítése:
    - platform_modules és app_modules KÜLÖN listákban maradnak
    - A startup_hooks sorrendje: platform hooks → modul hooks → app hooks
    - Minden modul-metadata (routers, permissions, stb.) a platform + app sorrendben kerül be

    FONTOS: Ez a függvény nem validálja a platform/app szétválasztást, csak
    összefésüli a listákat. A kétfázisú validáció a register_manifest_modules()-ban van.
    """
    # Teljes lista platform-először sorrendben (metaadatok gyűjtéséhez).
    # SORREND: platform first, then app – ez az egyetlen helyes sorrend.
    all_modules = platform_manifest.platform_modules + app_manifest.app_modules

    return PlatformManifest(
        app_name=app_manifest.app_name or platform_manifest.app_name,
        description=app_manifest.description if app_manifest.description is not None else platform_manifest.description,
        version=app_manifest.version or platform_manifest.version,
        docs_url=platform_manifest.docs_url,
        redoc_url=platform_manifest.redoc_url,
        bootstrap_hooks=platform_manifest.bootstrap_hooks + app_manifest.bootstrap_hooks,
        # ELKÜLÖNÍTETT LISTÁK – a bootstrap/modules.py kétfázisú regisztrációhoz szükséges.
        platform_modules=platform_manifest.platform_modules,
        app_modules=app_manifest.app_modules,
        # A következő mezők összesítő gyűjtők – platform sorrendben.
        routers=tuple(
            route
            for module in all_modules
            for route in module.routers()
        ),
        startup_hooks=(
            platform_manifest.startup_hooks
            + tuple(hook for module in all_modules for hook in module.startup_hooks())
            + app_manifest.startup_hooks
        ),
        shutdown_hooks=(
            platform_manifest.shutdown_hooks
            + tuple(hook for module in all_modules for hook in module.shutdown_hooks())
            + app_manifest.shutdown_hooks
        ),
        light_paths=tuple(path for module in all_modules for path in module.light_paths()),
        permissions=tuple(perm for module in all_modules for perm in module.permissions()),
        tenant_schema_hooks=tuple(
            hook for module in all_modules for hook in module.tenant_schema_hooks()
        ),
        ui_nav_meta=tuple(item for module in all_modules for item in module.ui_nav_meta()),
    )
