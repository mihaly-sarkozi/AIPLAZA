# backend/core/kernel/lifecycle/lifecycle.py
# Feladat: A kernel lifecycle komponenst regisztráló BaseAppModule implementáció. Beköti a DB/cache/background worker probe repositoryt, regisztrálja a LifecycleService-t, publikálja a health/metrics routert és startup/shutdown hookokkal vezeti a runtime állapotot. Core kernel assembly a futásállapot megfigyeléséhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.infrastructure.cache import get_cache
from core.kernel.deps.facade import get_service
from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.state_keys import CTX_STATE_OUTBOX_WORKER
from core.kernel.interface.routing import RouteRegistration
from core.kernel.interface.keys import PLATFORM_LIFECYCLE_SERVICE
from core.kernel.lifecycle.lifecycle_probe_repository import LifecycleProbeRepository
from core.kernel.lifecycle.lifecycle_router import root_probe_router, router as lifecycle_router
from core.kernel.lifecycle.lifecycle_service import LifecycleService


class LifecycleCoreModule(BaseAppModule):
    key = "platform.lifecycle"

    def register(self, container: ModuleContext) -> None:
        # OutboxWorker a module context state-ből (AppContainer állítja be a
        # modulregisztráció előtt). Web módban None -> check_background_worker "disabled".
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
        return (
            RouteRegistration(router=lifecycle_router, prefix="/api", tags=("platform-lifecycle",)),
            RouteRegistration(router=root_probe_router, prefix="", tags=("platform-lifecycle",)),
        )

    def light_paths(self) -> tuple[str, ...]:
        return ("/api/health", "/api/health/live", "/api/health/ready", "/api/livez", "/api/readyz", "/livez", "/readyz", "/api/metrics")

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
