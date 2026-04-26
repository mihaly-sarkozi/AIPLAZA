from __future__ import annotations

from apps._template.contracts import TEMPLATE_SERVICE
from apps._template.hooks import register_template_tenant_hooks
from apps._template.router import router
from apps._template.service import TemplateService
from apps.contracts import module_key, module_route_tag
from core.platform.contract import AppModule, ModuleContext, RouteRegistration


class TemplateAppModule(AppModule):
    """Reference backend app module.

    Allowed imports:
    - `core.platform.contract`
    - `core.platform.service_keys`
    - explicit extension contracts from `apps.contracts.public_api`

    Forbidden imports:
    - `core.platform.bootstrap.*`
    - `core.kernel.*` internals without allowlist
    - another app's implementation package
    """

    key = module_key("template")

    def register(self, container: ModuleContext) -> None:
        container.register_service(TEMPLATE_SERVICE, TemplateService())

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=router, prefix="/api", tags=(module_route_tag("template"),)),)

    def tenant_schema_hooks(self) -> tuple:
        return (register_template_tenant_hooks,)

    def permissions(self) -> tuple[str, ...]:
        return ("template.read",)


def get_module() -> AppModule:
    return TemplateAppModule()
