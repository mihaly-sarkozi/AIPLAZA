from __future__ import annotations


class KbCrudModule:
    name = "kb.crud"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_crud.bootstrap.service_keys import KB_CRUD_REPOSITORY
        from apps.kb.kb_crud.repository.KnowledgeBaseRepository import KnowledgeBaseRepository

        container.register_repository(
            KB_CRUD_REPOSITORY,
            KnowledgeBaseRepository(container.session_factory),
        )

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbCrudModule"]
