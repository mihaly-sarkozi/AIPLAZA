from __future__ import annotations

# backend/apps/kb/kb_understanding/module.py
# Feladat: A megértési (understanding) modul bekötése — repository-k regisztrálása.
# A pipeline összeszerelése a kompozíciós gyökérben történik (apps/kb/events.py),
# mert ott köthető hozzá a kb_ingest item-olvasó adapter.
# Sárközi Mihály - 2026.06.11


class KbUnderstandingModule:
    name = "kb.understanding"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_understanding.bootstrap.service_keys import (
            KB_UNDERSTANDING_CHUNK_REPOSITORY,
            KB_UNDERSTANDING_EMBEDDING_REPOSITORY,
            KB_UNDERSTANDING_ENTITY_REPOSITORY,
            KB_UNDERSTANDING_JOB_REPOSITORY,
            KB_UNDERSTANDING_STEP_RUN_REPOSITORY,
        )
        from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
        from apps.kb.kb_understanding.repository.EmbeddingRepository import EmbeddingRepository
        from apps.kb.kb_understanding.repository.EntityRepository import EntityRepository
        from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
            UnderstandingJobRepository,
        )
        from apps.kb.kb_understanding.repository.UnderstandingStepRunRepository import (
            UnderstandingStepRunRepository,
        )

        container.register_repository(
            KB_UNDERSTANDING_JOB_REPOSITORY,
            UnderstandingJobRepository(container.session_factory),
        )
        container.register_repository(
            KB_UNDERSTANDING_STEP_RUN_REPOSITORY,
            UnderstandingStepRunRepository(container.session_factory),
        )
        container.register_repository(
            KB_UNDERSTANDING_CHUNK_REPOSITORY,
            ChunkRepository(container.session_factory),
        )
        container.register_repository(
            KB_UNDERSTANDING_ENTITY_REPOSITORY,
            EntityRepository(container.session_factory),
        )
        container.register_repository(
            KB_UNDERSTANDING_EMBEDDING_REPOSITORY,
            EmbeddingRepository(container.session_factory),
        )

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbUnderstandingModule"]
