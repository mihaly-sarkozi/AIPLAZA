# backend/core/kernel/app/app_manifest.py
# Feladat: A teljes alkalmazás felépülését leíró runtime manifestet definiálja. Tartalmazza a core modulokat, app modulokat, route-regisztrációkat, lifecycle hookokat, jogosultságokat, tenant schema hookokat és frontend navigációs metaadatokat. A main/app factory, a modulregisztráció és több teszt is ezt használja, ezért ez a kernel általános alkalmazásleíró szerződése.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.types.lifecycle_hook_types import BootstrapHook, LifecycleHook, TenantSchemaRegistrar
from core.kernel.interface.routing import RouteRegistration


@dataclass(frozen=True)
class AppManifest:
    app_name: str  # Az alkalmazás neve, FastAPI title és dokumentációs név.
    description: str = ""  # Rövid app leírás, OpenAPI dokumentációhoz.
    version: str = "1.0"  # Publikus app/API verzió.
    bootstrap_hooks: tuple[BootstrapHook, ...] = ()  # App összeállítás előtti init/bekötési hookok.
    core_modules: tuple[BaseAppModule, ...] = ()  # Kötelező platform/core modulok, mindig először regisztrálódnak.
    app_modules: tuple[BaseAppModule, ...] = ()  # Telepített addon/app modulok, a core után regisztrálódnak.
    routers: tuple[RouteRegistration, ...] = ()  # FastAPI router bekötések prefix/tag adatokkal.
    startup_hooks: tuple[LifecycleHook, ...] = ()  # FastAPI lifespan startup alatt lefutó hookok.
    shutdown_hooks: tuple[LifecycleHook, ...] = ()  # FastAPI lifespan shutdown alatt lefutó takarító hookok.
    light_paths: tuple[str, ...] = ()  # Könnyített auth/middleware útvonalak, pl. health vagy public endpointok.
    permissions: tuple[str, ...] = ()  # Modulok által deklarált jogosultságkulcsok.
    tenant_schema_hooks: tuple[TenantSchemaRegistrar, ...] = ()  # Tenant séma migráció/provisioning regisztrálók.
    ui_nav_meta: tuple[dict[str, Any], ...] = field(default_factory=tuple)  # Frontend navigációs metaadatok.

    # Egyben lekérhető az összes modul a regisztrációs sorrendben
    @property
    def modules(self) -> tuple[BaseAppModule, ...]:
        return self.core_modules + self.app_modules

    # Az app manifest inicializálása: app config + kötelező core modulok
    @classmethod
    def init_app(cls) -> "AppManifest":
        from core.kernel.config.config_loader import get_settings

        # A rendszer configurációját betöltjük
        settings = get_settings()
        
        # A kötelező core manifestet betöltjük
        core_manifest = cls.load_core()
        
        # Az app metadata-t a configurációból származtatjuk
        app_metadata = core_manifest.with_app_metadata(
            app_name=settings.app_name,
            description=settings.app_description,
            version=settings.app_version,
        )
        return app_metadata

    # A kötelező core modulok betöltése a manifestbe
    @classmethod
    def load_core(cls) -> "AppManifest":
        from admin.admin import AdminCoreModule
        from core.modules.auth.auth import AuthCoreModule
        from core.modules.brand.brand import BrandCoreModule
        from core.kernel.domain.module import DomainCoreModule
        from core.kernel.lifecycle.lifecycle import LifecycleCoreModule
        from core.modules.settings.settings import SettingsCoreModule
        from core.modules.tenant.tenant import TenantCoreModule
        from core.modules.users.users import UsersCoreModule

        core_modules = (
            # 1. Lifecycle: health/readiness – nincs platformfüggőség
            LifecycleCoreModule(),
            # 2. Settings: PLATFORM_SETTINGS_SERVICE – auth + tenant használja
            SettingsCoreModule(),
            # 3. Users: PLATFORM_USERS_SERVICE – tenant signup használja
            UsersCoreModule(),
            # 4. Auth: PLATFORM_SETTINGS_SERVICE + PLATFORM_CLOCK_SERVICE szükséges
            AuthCoreModule(),
            # 5. Admin: public sémás főadmin auth és user-kezelés
            AdminCoreModule(),
            # 6. Tenant: PLATFORM_USERS_SERVICE + PLATFORM_CLOCK_SERVICE szükséges
            TenantCoreModule(),
            # 7. Domain: PLATFORM_TENANT_LIFECYCLE_POLICY szükséges (tenant regisztrálja)
            DomainCoreModule(),
            # 8. Brand: PLATFORM_TENANT_LIFECYCLE_POLICY szükséges (tenant regisztrálja)
            BrandCoreModule(),
        )
        return cls(
            app_name="Platform API",
            description="Core platform API.",
            version="1.0",
            core_modules=core_modules,
        )

    def with_app_metadata(self, *, app_name: str, description: str, version: str) -> "AppManifest":
        return AppManifest(
            app_name=app_name or self.app_name,
            description=description if description is not None else self.description,
            version=version or self.version,
            bootstrap_hooks=self.bootstrap_hooks,
            core_modules=self.core_modules,
            app_modules=self.app_modules,
            routers=self.routers,
            startup_hooks=self.startup_hooks,
            shutdown_hooks=self.shutdown_hooks,
            light_paths=self.light_paths,
            permissions=self.permissions,
            tenant_schema_hooks=self.tenant_schema_hooks,
            ui_nav_meta=self.ui_nav_meta,
        )

    # Az addon/app modulok hozzáadása a manifesthez
    def add_modules(self, modules: Iterable[BaseAppModule]) -> "AppManifest":
        app_modules = tuple(modules)
        all_modules = self.core_modules + self.app_modules + app_modules
        return AppManifest(
            app_name=self.app_name,
            description=self.description,
            version=self.version,
            bootstrap_hooks=(
                self.bootstrap_hooks
                + tuple(hook for module in all_modules for hook in module.bootstrap_hooks())
            ),
            core_modules=self.core_modules,
            app_modules=self.app_modules + app_modules,
            routers=tuple(route for module in all_modules for route in module.routers()),
            startup_hooks=(
                self.startup_hooks
                + tuple(hook for module in all_modules for hook in module.startup_hooks())
            ),
            shutdown_hooks=(
                self.shutdown_hooks
                + tuple(hook for module in all_modules for hook in module.shutdown_hooks())
            ),
            light_paths=tuple(path for module in all_modules for path in module.light_paths()),
            permissions=tuple(perm for module in all_modules for perm in module.permissions()),
            tenant_schema_hooks=tuple(
                hook for module in all_modules for hook in module.tenant_schema_hooks()
            ),
            ui_nav_meta=tuple(item for module in all_modules for item in module.ui_nav_meta()),
        )


__all__ = ["AppManifest"]
