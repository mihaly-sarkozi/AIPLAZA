from __future__ import annotations

class KbUnderstandingModule:
    name = "kb.understanding"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_understanding.bootstrap.service_keys import (
            KB_UNDERSTANDING_CHUNK_REPOSITORY,
            KB_UNDERSTANDING_JOB_REPOSITORY,
        )
        from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
        from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
            UnderstandingJobRepository,
        )

        container.register_repository(
            KB_UNDERSTANDING_JOB_REPOSITORY,
            UnderstandingJobRepository(container.session_factory),
        )
        container.register_repository(
            KB_UNDERSTANDING_CHUNK_REPOSITORY,
            ChunkRepository(container.session_factory),
        )

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbUnderstandingModule"]
