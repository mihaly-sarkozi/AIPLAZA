from __future__ import annotations


class KbIndexingModule:
    name = "kb.indexing"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        from apps.kb.kb_indexing.bootstrap.service_keys import (
            KB_INDEXED_CHUNK_REPOSITORY,
            KB_INDEXING_JOB_REPOSITORY,
        )
        from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository
        from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository

        sf = container.session_factory
        container.register_repository(KB_INDEXING_JOB_REPOSITORY, IndexingJobRepository(sf))
        container.register_repository(KB_INDEXED_CHUNK_REPOSITORY, IndexedChunkRepository(sf))

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbIndexingModule"]
