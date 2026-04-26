# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from core.capabilities.cache import get_cache
from core.di import get_service
from core.platform.composition import AppModule, ModuleContext
from core.platform.contract.state_keys import CTX_STATE_OUTBOX_WORKER
from core.platform.contract.routing import RouteRegistration
from core.platform.lifecycle.repositories import LifecycleProbeRepository
from core.platform.lifecycle.router import router as lifecycle_router
from core.platform.lifecycle.services import LifecycleService
from core.platform.service_keys import PLATFORM_LIFECYCLE_SERVICE


class LifecyclePlatformModule(AppModule):
    key = "platform.lifecycle"

    def register(self, container: ModuleContext) -> None:
        # OutboxWorker a module context state-ből (AppContainer állítja be a
        # modulregisztráció előtt). Web módban None → check_background_worker "disabled".
        outbox_worker = container.get_state(CTX_STATE_OUTBOX_WORKER, None)
        probe_repository = LifecycleProbeRepository(
            container.infrastructure.db_session_factory,
            cache_backend=get_cache(),
            background_worker_probe=outbox_worker,
        )

        service = LifecycleService(
            probe_repository=probe_repository,
        )
        container.register_service(PLATFORM_LIFECYCLE_SERVICE, service)

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=lifecycle_router, prefix="/api", tags=("platform-lifecycle",)),)

    def light_paths(self) -> tuple[str, ...]:
        return ("/api/health", "/api/health/live", "/api/health/ready")

    def startup_hooks(self) -> tuple:
        async def _startup(app):
            service = get_service(PLATFORM_LIFECYCLE_SERVICE)
            try:
                service.mark_startup_begin()
                service.mark_startup_complete()
            except Exception as exc:
                service.mark_startup_error(exc)
                raise

        return (_startup,)

    def shutdown_hooks(self) -> tuple:
        async def _shutdown(app):
            service = get_service(PLATFORM_LIFECYCLE_SERVICE)
            try:
                service.mark_shutdown_begin()
            except Exception as exc:
                service.mark_shutdown_error(exc)
                raise

        return (_shutdown,)


def get_module() -> AppModule:
    return LifecyclePlatformModule()
