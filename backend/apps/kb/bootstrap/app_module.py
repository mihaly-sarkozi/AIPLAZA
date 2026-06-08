# backend/apps/kb/bootstrap/app_module.py
# Feladat: A kb app platform belépési pontja (BaseAppModule). 
# Regisztrálja a hét almodul service-eit és event handler-eit, 
# köti be a fő routert és deklarálja a kb.* jogosultságokat.
# Sárközi Mihály - 2026.06.07

from __future__ import annotations

from apps.kb.kb_crud.module import KbCrudModule
from apps.kb.kb_feedback.module import KbFeedbackModule
from apps.kb.kb_maintenance.module import KbMaintenanceModule
from apps.kb.kb_reading.module import KbReadingModule
from apps.kb.kb_training.module import KbTrainingModule
from apps.kb.kb_search.module import KbSearchModule
from apps.kb.kb_testing.module import KbTestingModule
from apps.kb.kb_understanding.module import KbUnderstandingModule
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key, module_route_tag

KB_MODULES = [
    KbCrudModule(),
    KbReadingModule(),
    KbTrainingModule(),
    KbUnderstandingModule(),
    KbSearchModule(),
    KbTestingModule(),
    KbFeedbackModule(),
    KbMaintenanceModule(),
]


class KbAppModule(BaseAppModule):
    key = module_key("kb")

    def register(self, container: ModuleContext) -> None:
        from apps.kb.bootstrap.service_keys import KB_FILE_STORAGE
        from infra.kb import MinioFileStorage

        container.register_repository(KB_FILE_STORAGE, MinioFileStorage())

        for module in KB_MODULES:
            module.register_services(container)

        if getattr(container.security, "dispatcher", None) is not None:
            from apps.kb.events import register_kb_event_handlers

            register_kb_event_handlers(container.security.dispatcher)

        event_bus = container.get_state("event_bus", None)
        if event_bus is not None:
            for module in KB_MODULES:
                module.register_event_handlers(event_bus)

    def routers(self) -> tuple[RouteRegistration, ...]:
        from apps.kb.router import router as kb_router

        return (
            RouteRegistration(
                router=kb_router,
                prefix="/api",
                tags=(module_route_tag("kb"),),
            ),
        )

    def permissions(self) -> tuple[str, ...]:
        return (
            "kb.read",
            "kb.write",
            "kb.train",
            "kb.admin",
        )

    def tenant_schema_hooks(self) -> tuple:
        from apps.kb.kb_reading.bootstrap.tenant_hooks import register_kb_reading_tenant_hooks
        from apps.kb.kb_training.bootstrap.tenant_hooks import register_kb_training_tenant_hooks

        return (
            register_kb_reading_tenant_hooks,
            register_kb_training_tenant_hooks,
        )


def get_module() -> BaseAppModule:
    return KbAppModule()


__all__ = ["KB_MODULES", "KbAppModule", "get_module"]
