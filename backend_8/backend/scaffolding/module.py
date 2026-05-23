# backend/scaffolding/module.py
# Feladat: Az új app modulok backend `module.py` sablonját adja. A TemplateAppModule példán keresztül megmutatja a BaseAppModule implementációt, service regisztrációt, router bekötést, permission listát és get_module() factoryt. Scaffolding template fájl, amelyet a create_app_module script névcserével másol az apps alá.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key, module_route_tag
from core.kernel.interface.app_keys import module_service_key

from .router import router
from .service import TemplateService

TEMPLATE_SERVICE = module_service_key("template")


class TemplateAppModule(BaseAppModule):
    key = module_key("template")

    def register(self, container: ModuleContext) -> None:
        container.register_service(TEMPLATE_SERVICE, TemplateService())

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=router, prefix="/api", tags=(module_route_tag("template"),)),)

    def permissions(self) -> tuple[str, ...]:
        return ("template.read",)


def get_module() -> BaseAppModule:
    return TemplateAppModule()
