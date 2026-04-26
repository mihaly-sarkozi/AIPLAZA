# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from apps.contracts import module_key
from apps.contracts.service_keys import MODULE_CHAT_LLM_CLIENT_FACTORY, MODULE_CHAT_SERVICE, MODULE_KNOWLEDGE_SERVICE
from apps.chat.infrastructure import build_chat_infrastructure
from apps.chat.router.chat_router import router as chat_router
from apps.state_keys import CTX_STATE_CHAT_INFRASTRUCTURE
from core.platform.contract import AppModule, ModuleContext, RouteRegistration


class ChatModule(AppModule):
    key = module_key("chat")

    def optional_service_dependencies(self) -> tuple[str, ...]:
        return (MODULE_KNOWLEDGE_SERVICE,)

    # Ez a metódus regisztrálja a(z) register logikáját.
    def register(self, container: ModuleContext) -> None:
        infra = build_chat_infrastructure(
            knowledge_service=container.get_optional_service(MODULE_KNOWLEDGE_SERVICE),
        )
        service = infra.build_chat_service()
        container.set_state(CTX_STATE_CHAT_INFRASTRUCTURE, infra)
        container.register_factory(MODULE_CHAT_LLM_CLIENT_FACTORY, infra.build_llm_client)
        container.register_service(MODULE_CHAT_SERVICE, service)

    # Ez a metódus a(z) routers logikáját valósítja meg.
    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=chat_router, prefix="/api", tags=("chat",)),)

    # Ez a metódus a(z) light_paths logikáját valósítja meg.
    def light_paths(self) -> tuple[str, ...]:
        return ("/api/chat",)

    # Ez a metódus a(z) permissions logikáját valósítja meg.
    def permissions(self) -> tuple[str, ...]:
        return ("chat.use",)

    # Ez a metódus a(z) ui_nav_meta logikáját valósítja meg.
    def ui_nav_meta(self) -> tuple[dict[str, str], ...]:
        return ({"id": "chat", "label": "Chat", "path": "/chat"},)


# Ez a függvény visszaadja a(z) modul logikáját.
def get_module() -> AppModule:
    return ChatModule()
