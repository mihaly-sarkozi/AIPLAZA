# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from apps.knowledge.api.router import router as knowledge_router
from apps.knowledge.bootstrap.service_keys import (
    KNOWLEDGE_EMBEDDING_SERVICE_FACTORY,
    KNOWLEDGE_EVENT_CHANNEL,
    KNOWLEDGE_QDRANT_FACTORY,
    KNOWLEDGE_REPOSITORY,
    KNOWLEDGE_SERVICE,
)
from apps.knowledge.bootstrap.tenant_hooks import register_knowledge_tenant_hooks, register_knowledge_tenant_signup_hook
from apps.knowledge.infrastructure import build_knowledge_infrastructure
from apps.state_keys import CTX_STATE_KNOWLEDGE_INFRASTRUCTURE
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key


class KnowledgeModule(BaseAppModule):
    key = module_key("knowledge")

    # Ez a metódus regisztrálja a(z) register logikáját.
    def register(self, container: ModuleContext) -> None:
        infra = build_knowledge_infrastructure(
            db_session_factory=container.infrastructure.db_session_factory,
            user_repository=container.infrastructure.repositories.user_repo,
        )
        repo = infra.build_repository()
        service = infra.build_service(repo)
        container.set_state(CTX_STATE_KNOWLEDGE_INFRASTRUCTURE, infra)
        container.register_repository(KNOWLEDGE_REPOSITORY, repo)
        container.register_factory(KNOWLEDGE_EMBEDDING_SERVICE_FACTORY, infra.build_embedding_service)
        container.register_factory(KNOWLEDGE_QDRANT_FACTORY, infra.build_qdrant_client)
        container.register_service(KNOWLEDGE_SERVICE, service)
        if getattr(container.security, "event_channel", None) is not None:
            container.register_service(KNOWLEDGE_EVENT_CHANNEL, container.security.event_channel)
        from apps.knowledge.events import register_knowledge_event_handlers
        register_knowledge_event_handlers(container.security.dispatcher)
        register_knowledge_tenant_signup_hook(service)

    # Ez a metódus a(z) routers logikáját valósítja meg.
    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=knowledge_router, prefix="/api", tags=("knowledge",)),)

    # Ez a metódus a(z) tenant_schema_hooks logikáját valósítja meg.
    def tenant_schema_hooks(self) -> tuple:
        return (register_knowledge_tenant_hooks,)

    # Ez a metódus a(z) permissions logikáját valósítja meg.
    def permissions(self) -> tuple[str, ...]:
        return (
            "knowledge.read",
            "knowledge.write",
            "knowledge.permissions.manage",
        )

    # Ez a metódus a(z) ui_nav_meta logikáját valósítja meg.
    def ui_nav_meta(self) -> tuple[dict[str, str], ...]:
        return ({"id": "knowledge", "label": "Knowledge", "path": "/knowledge"},)


# Ez a függvény visszaadja a(z) modul logikáját.
def get_module() -> BaseAppModule:
    return KnowledgeModule()


__all__ = ["KnowledgeModule", "get_module"]
