# backend/core/kernel/app/app_container.py
# Feladat: Az alkalmazás runtime konténerét építi fel és ad hozzáférést a központi szolgáltatásokhoz. Összeköti az infrastruktúrát, security réteget, modulregisztrációt, DI bekötést és lifecycle kontrollert, majd ezeket a FastAPI dependency réteg és a lifespan használja. Core keretrendszer-elem, mert általános composition root szerepet lát el, üzleti app-specifikus döntések nélkül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from threading import RLock

from core.kernel.app.app_manifest import AppManifest
from core.kernel.runtime.clock import SystemClock
from core.kernel.interface.keys import (
    PLATFORM_AUTH_TWO_FACTOR_SERVICE,
    PLATFORM_LOGIN_SERVICE,
    PLATFORM_LOGOUT_SERVICE,
    PLATFORM_REFRESH_SERVICE,
    PLATFORM_TENANT_SIGNUP_FACTORY,
)
from core.kernel.bootstrap.infrastructure import build_infrastructure
from core.kernel.runtime.kernel_di_wiring import wire_kernel_dependencies
from core.kernel.runtime.module_registration import register_modules
from core.kernel.runtime.outbox_wiring import wire_outbox_worker
from core.kernel.runtime.permission_wiring import assemble_permission_service
from core.kernel.runtime.runtime_lifecycle import RuntimeLifecycleController
from core.kernel.runtime.security_wiring import assemble_security_layer
from core.modules.tenant.helpers import tenant_frontend_base_url_for_slug


def get_container(manifest: AppManifest | None = None) -> "AppContainer":
    
    # Ha nincs manifest, akkor a legutóbbi aktív manifestet használjuk
    global _active_container, _active_manifest
    
    if manifest is None:
        if _active_manifest is None:
            raise RuntimeError("AppManifest nincs beállítva a runtime konténerhez.")
        manifest = _active_manifest
    elif manifest != _active_manifest:
        _active_manifest = manifest
        _active_container = None
    
    # Több párhuzamos kérés ugyanazon cold-start alatt ne építsen külön konténert.
    with _container_build_lock:
        if _active_container is None:
            _active_container = AppContainer(manifest)
        return _active_container

# AppContainer osztály, amely a runtime konténert reprezentálja
class AppContainer:
    
    # AppContainer osztály, amely a runtime konténert reprezentálja
    def __init__(self, manifest: AppManifest) -> None:
        
        self._manifest = manifest

        # Infrastruktúra összeállítása
        infrastructure = build_infrastructure()
        self._infrastructure = infrastructure
        
        # Repositories lekérése az InfrastructureRegistry-ből
        repos = infrastructure.repositories
        self._tenant_repo = repos.tenant_repo
        self._user_repo = repos.user_repo
        self._session_repo = repos.session_repo
        self._audit_repo = repos.audit_repo

        # 2) idő beállítása
        self._clock = SystemClock()
        
        # Biztonsági réteg összeállítása
        self._audit_service, self._event_outbox_repo, self._security = assemble_security_layer(
            infrastructure=infrastructure,
            clock=self._clock,
        )
        
        # Token service, event channel, dispatcher lekérése a SecurityRegistry-ből
        self._token_service = self._security.token_service
        
        # Event channel, dispatcher lekérése a SecurityRegistry-ből
        self._event_channel = self._security.event_channel
        self._dispatcher = self._security.dispatcher

        # 3) Event / outbox worker wiring (indítás később: lifecycle)
        self._outbox_worker = wire_outbox_worker(self._event_outbox_repo, self._security)

        # 4) Manifest + jogosultságok
        manifest = self._manifest
        self._permission_service = assemble_permission_service(manifest)

        # 5) Modul regisztráció (platform → app)
        modules = register_modules(
            infrastructure=infrastructure,
            security=self._security,
            manifest=manifest,
            outbox_worker=self._outbox_worker,
        )
        
        # Module context lekérése a ModuleRegistry-ből
        self._module_context = modules.module_context
        
        # Two factor service, login service, refresh service, logout service lekérése a ModuleContext-ből
        self._two_factor_service = self._module_context.get_service(PLATFORM_AUTH_TWO_FACTOR_SERVICE)
        
        # Login service, refresh service, logout service lekérése a ModuleContext-ből
        self._login_service = self._module_context.get_service(PLATFORM_LOGIN_SERVICE)
        
        # Refresh service, logout service lekérése a ModuleContext-ből
        self._refresh_service = self._module_context.get_service(PLATFORM_REFRESH_SERVICE)
        
        # Logout service lekérése a ModuleContext-ből
        self._logout_service = self._module_context.get_service(PLATFORM_LOGOUT_SERVICE)

        # 6) Kernel DI
        wire_kernel_dependencies(
            audit_service=self._audit_service,
            token_service=self._token_service,
            login_service=self._login_service,
            refresh_service=self._refresh_service,
            logout_service=self._logout_service,
            permission_service=self._permission_service,
            event_channel=self._event_channel,
            infrastructure=infrastructure,
        )

        # 7) Lifecycle (storage init, worker start/stop)
        self._lifecycle = RuntimeLifecycleController(
            infrastructure=infrastructure,
            outbox_worker=self._outbox_worker,
        )

    # Outbox tábla létrehozása és scaling guard-ok ellenőrzése
    def initialize_runtime_storage(self) -> None:
        self._lifecycle.initialize_runtime_storage()

    # Háttérszolgáltatások indítása az InstanceRole figyelembevételével
    def start_runtime_services(self) -> None:
        self._lifecycle.start_runtime_services()

    # OutboxWorker aktuális állapotának lekérése (lifecycle endpoint-hez)
    def outbox_worker_status(self) -> str:
        return self._lifecycle.outbox_worker_status()

    # Tenant repository lekérése a ModuleContext-ből
    def get_tenant_repository(self):
        return self._tenant_repo

    # Session scope lekérése a ModuleContext-ből
    def session_scope(self):
        return self._infrastructure.db_session_factory()

    # Service lekérése a ModuleContext-ből
    def get_registered_service(self, name: str):
        return self._module_context.get_service(name)

    # Repository lekérése a ModuleContext-ből
    def get_registered_repository(self, name: str):
        return self._module_context.get_repository(name)

    # Factory lekérése a ModuleContext-ből
    def get_registered_factory(self, name: str):
        return self._module_context.get_factory(name)

    # Tenant signup service lekérése a ModuleContext-ből
    def build_tenant_signup_service(self, request_base_url_builder):
        return self._module_context.get_factory(PLATFORM_TENANT_SIGNUP_FACTORY)(request_base_url_builder)

    # Tenant signup service lekérése a ModuleContext-ből
    def build_tenant_signup_service_for_request(self, request):
        return self.build_tenant_signup_service(
            lambda slug: tenant_frontend_base_url_for_slug(request, slug),
        )

    # Háttérszolgáltatások leállítása (lifespan shutdown hook)
    def shutdown(self) -> None:
        """Leállítja a háttérszolgáltatásokat (lifespan shutdown hook)."""
        self._lifecycle.shutdown()


class _LazyContainerProxy:
    def __getattr__(self, name):
        return getattr(get_container(), name)


_container_build_lock = RLock()
_active_manifest: AppManifest | None = None
_active_container: AppContainer | None = None
container = _LazyContainerProxy()


__all__ = ["AppContainer", "container", "get_container"]
