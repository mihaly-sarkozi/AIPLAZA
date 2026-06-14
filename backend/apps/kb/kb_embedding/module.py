from __future__ import annotations


class KbEmbeddingModule:
    name = "kb.embedding"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        from apps.kb.kb_embedding.bootstrap.service_keys import (
            KB_EMBEDDING_JOB_REPOSITORY,
            KB_EMBEDDING_REPOSITORY,
        )
        from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
        from apps.kb.kb_embedding.repository.KnowledgeEmbeddingRepository import KnowledgeEmbeddingRepository

        sf = container.session_factory
        container.register_repository(KB_EMBEDDING_JOB_REPOSITORY, EmbeddingJobRepository(sf))
        container.register_repository(KB_EMBEDDING_REPOSITORY, KnowledgeEmbeddingRepository(sf))

    def register_event_handlers(self, event_bus) -> None:
        # Event handlers: apps/kb/events.py (canonical wiring)
        pass


__all__ = ["KbEmbeddingModule"]
