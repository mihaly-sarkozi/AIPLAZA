from __future__ import annotations

# backend/apps/kb/kb_search/module.py
# Feladat: kb_search modul service és router regisztráció.


class KbSearchModule:
    name = "kb.search"

    def register_routes(self, app) -> None:
        from apps.kb.kb_search.router.SearchRouter import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_search.bootstrap.search_assembly import build_search_services
        from apps.kb.kb_search.bootstrap.service_keys import (
            KB_SEARCH_CHAT_FACADE,
            KB_SEARCH_PIPELINE,
            KB_SEARCH_RUN_REPOSITORY,
        )
        from apps.state_keys import KNOWLEDGE_SERVICE

        access_checker = container.get_optional_service(KNOWLEDGE_SERVICE)
        services = build_search_services(
            session_factory=container.session_factory,
            access_checker=access_checker,
        )
        container.register_service(KB_SEARCH_CHAT_FACADE, services.chat_facade)
        container.register_service(KB_SEARCH_PIPELINE, services.pipeline)
        container.register_repository(KB_SEARCH_RUN_REPOSITORY, services.run_repository)

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbSearchModule"]
