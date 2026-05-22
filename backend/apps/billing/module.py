# backend/apps/billing/module.py
# Feladat: A billing app BaseAppModule assembly implementációja. Létrehozza a BillingService-t, regisztrálja a tenant usage service kulcson, beköti a routert, startupkor storage/catalog inicializálást és due cycle futtatást végez, valamint background workert indít. Program-specifikus modulösszeszerelés.
# Sárközi Mihály - 2026.05.21

"""Billing app modul – helyes interface-alapú minta.

Importálás: kizárólag core.kernel.interface-ből (stabil platformfelület).
Raw string service lookup-ok NINCSENEK – typed accessorok és konstansok.
"""
from __future__ import annotations

from core.kernel.interface.app_conventions import module_key
from apps.billing.repositories import BillingRepository
from apps.billing.router import router as billing_router
from apps.billing.service import BillingService
from apps.billing.tenant_hooks import register_billing_tenant_signup_hook
from apps.billing.worker import BillingWorker
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.keys import PLATFORM_CLOCK, PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.process import should_run_background_workers
from core.modules.settings.registry.settings_section_registry import SettingsSection, register_settings_section


class BillingAppModule(BaseAppModule):
    key = module_key("billing")

    def service_dependencies(self) -> tuple[str, ...]:
        """PLATFORM_CLOCK szükséges a BillingService-hez."""
        return (PLATFORM_CLOCK,)

    def register(self, ctx: ModuleContext) -> None:
        # Typed property-k: nincs raw string lookup
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
        return ("billing.read", "billing.write")


def get_module() -> BaseAppModule:
    return BillingAppModule()
