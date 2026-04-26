"""Alkalmazás runtime konténer.

Felépíti és összeköti a platform-szintű komponenseket úgy, hogy a konkrét
összeállítási lépések külön assembly modulokban élnek (lásd ``assembly/``).

Az ``AppContainer`` vékony koordinátor: delegál az infrastruktúra-, security-,
manifest-, modul-regisztrációs és lifecycle-assembly-knek; nem tartalmazza
a „god object” mintát.

InstanceRole-tudatos startup:
  - INSTANCE_ROLE=web      → nincs OutboxWorker szál (worker process végzi)
  - INSTANCE_ROLE=combined → OutboxWorker szál indul (fejlesztői mód)
  - INSTANCE_ROLE=worker   → standalone __main__.py futtatja, nem AppContainer

Futtatási kontextusok:
  Request path:  DB session, auth, DI → AppContainer-en keresztül
  Background:    OutboxWorker → outbox polling + EventDispatcher (worker.py)
"""
from __future__ import annotations

from collections.abc import Callable

from core.extensions.tenant.helpers import tenant_frontend_base_url_for_slug
from core.kernel.clock import SystemClock
from core.platform.manifest import AppManifest
from core.platform.runtime.assembly.infrastructure_assembly import assemble_infrastructure
from core.platform.runtime.assembly.kernel_di import wire_kernel_dependencies
from core.platform.runtime.assembly.manifest_assembly import load_merged_manifest
from core.platform.runtime.assembly.module_registration import register_modules
from core.platform.runtime.assembly.outbox_wiring import wire_outbox_worker
from core.platform.runtime.assembly.permissions_assembly import assemble_permission_service
from core.platform.runtime.assembly.runtime_lifecycle import RuntimeLifecycleController
from core.platform.runtime.assembly.security_assembly import assemble_security_layer
from core.platform.service_keys import (
    PLATFORM_AUTH_TWO_FACTOR_SERVICE,
    PLATFORM_LOGIN_SERVICE,
    PLATFORM_LOGOUT_SERVICE,
    PLATFORM_REFRESH_SERVICE,
    PLATFORM_TENANT_SIGNUP_FACTORY,
)


class AppContainer:
    """Koordináló runtime konténer – ugyanaz a publikus API, mint korábban."""

    def __init__(self, manifest_loader: Callable[[], AppManifest]) -> None:
        self._manifest_loader = manifest_loader

        # 1) Infrastruktúra
        infrastructure = assemble_infrastructure()
        self._infrastructure = infrastructure
        repos = infrastructure.repositories
        self._tenant_repo = repos.tenant_repo
        self._user_repo = repos.user_repo
        self._session_repo = repos.session_repo
        self._audit_repo = repos.audit_repo

        # 2) Óra + biztonsági réteg (token, channel, dispatcher, proxyzott audit/email)
        self._clock = SystemClock()
        self._audit_service, self._event_outbox_repo, self._security = assemble_security_layer(
            infrastructure=infrastructure,
            clock=self._clock,
        )
        self._token_service = self._security.token_service
        self._event_channel = self._security.event_channel
        self._dispatcher = self._security.dispatcher

        # 3) Event / outbox worker wiring (indítás később: lifecycle)
        self._outbox_worker = wire_outbox_worker(self._event_outbox_repo, self._security)

        # 4) Manifest merge + jogosultságok
        manifest = load_merged_manifest(self._manifest_loader)
        self._manifest = manifest
        self._permission_service = assemble_permission_service(manifest)

        # 5) Modul regisztráció (platform → app)
        modules = register_modules(
            infrastructure=infrastructure,
            security=self._security,
            manifest=manifest,
            outbox_worker=self._outbox_worker,
        )
        self._module_context = modules.module_context
        self._two_factor_service = self._module_context.get_service(PLATFORM_AUTH_TWO_FACTOR_SERVICE)
        self._login_service = self._module_context.get_service(PLATFORM_LOGIN_SERVICE)
        self._refresh_service = self._module_context.get_service(PLATFORM_REFRESH_SERVICE)
        self._logout_service = self._module_context.get_service(PLATFORM_LOGOUT_SERVICE)

        # 6) Kernel DI
        wire_kernel_dependencies(
            audit_service=self._audit_service,
            token_service=self._token_service,
            login_service=self._login_service,
            refresh_service=self._refresh_service,
            logout_service=self._logout_service,
            permission_service=self._permission_service,
            infrastructure=infrastructure,
        )

        # 7) Lifecycle (storage init, worker start/stop)
        self._lifecycle = RuntimeLifecycleController(
            infrastructure=infrastructure,
            outbox_worker=self._outbox_worker,
        )

    def initialize_runtime_storage(self) -> None:
        """Outbox tábla létrehozása és scaling guard-ok ellenőrzése."""
        self._lifecycle.initialize_runtime_storage()

    def start_runtime_services(self) -> None:
        """Háttérszolgáltatások indítása az InstanceRole figyelembevételével."""
        self._lifecycle.start_runtime_services()

    def outbox_worker_status(self) -> str:
        """Az OutboxWorker aktuális állapota (lifecycle endpoint-hoz)."""
        return self._lifecycle.outbox_worker_status()

    def get_tenant_repository(self):
        return self._tenant_repo

    def session_scope(self):
        return self._infrastructure.db_session_factory()

    def get_registered_service(self, name: str):
        return self._module_context.get_service(name)

    def get_registered_repository(self, name: str):
        return self._module_context.get_repository(name)

    def get_registered_factory(self, name: str):
        return self._module_context.get_factory(name)

    def build_tenant_signup_service(self, request_base_url_builder):
        return self._module_context.get_factory(PLATFORM_TENANT_SIGNUP_FACTORY)(request_base_url_builder)

    def build_tenant_signup_service_for_request(self, request):
        return self.build_tenant_signup_service(
            lambda slug: tenant_frontend_base_url_for_slug(request, slug),
        )

    def shutdown(self) -> None:
        """Leállítja a háttérszolgáltatásokat (lifespan shutdown hook)."""
        self._lifecycle.shutdown()
