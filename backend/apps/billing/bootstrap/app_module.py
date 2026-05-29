# backend/apps/billing/bootstrap/module.py
# Feladat: A billing app BaseAppModule assembly implementációja. Létrehozza a BillingService-t, beköti a routert, tenant hookot és worker lifecycle-t.
# Sárközi Mihály - 2026.05.24

"""Billing app modul – helyes interface-alapú minta."""
from __future__ import annotations

from apps.billing.bootstrap.tenant_hooks import register_billing_tenant_signup_hook
from apps.billing.repositories import BillingRepository
from apps.billing.router import router as billing_router
from apps.billing.service import BillingService
from apps.billing.worker import BillingWorker
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key
from core.kernel.interface.keys import PLATFORM_CLOCK, PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.process import should_run_background_workers
from core.modules.settings.registry.settings_section_registry import SettingsSection, register_settings_section


class BillingAppModule(BaseAppModule):
    key = module_key("billing")

    def service_dependencies(self) -> tuple[str, ...]:
        """PLATFORM_CLOCK szükséges a BillingService-hez."""
        return (PLATFORM_CLOCK,)

    def register(self, ctx: ModuleContext) -> None:
        service = BillingService(
            repo=BillingRepository(ctx.session_factory),
            tenant_repo=ctx.tenant_repository,
            session_factory=ctx.session_factory,
            user_repository=ctx.user_repository,
            email_service=ctx.email_service,
            clock=ctx.clock,
        )
        worker = BillingWorker()
        ctx.register_service(PLATFORM_TENANT_USAGE_SERVICE, service)
        self._billing_service = service
        self._billing_worker = worker
        self._session_factory = ctx.session_factory
        register_billing_tenant_signup_hook(service)
        register_settings_section(
            SettingsSection(
                key="billing",
                label="Billing",
                path="/admin/settings?section=billing",
                permission="settings.read",
                order=40,
                description="Előfizetés, limit és használat.",
                source="app.billing",
            )
        )

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=billing_router, prefix="/api", tags=("platform-billing",)),)

    def startup_hooks(self) -> tuple:
        async def _startup(app) -> None:
            if self._session_factory.engine.dialect.name == "sqlite":
                return
            self._billing_service.ensure_storage()
            self._billing_service.process_due_cycles()
            if should_run_background_workers():
                self._billing_worker.start()

        return (_startup,)

    def shutdown_hooks(self) -> tuple:
        async def _shutdown(app) -> None:
            if should_run_background_workers():
                self._billing_worker.stop()

        return (_shutdown,)

    def permissions(self) -> tuple[str, ...]:
        return ("billing.read", "billing.write", "billing.manage")


def get_module() -> BaseAppModule:
    return BillingAppModule()


__all__ = ["BillingAppModule", "get_module"]
