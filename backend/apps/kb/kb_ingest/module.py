from __future__ import annotations

# backend/apps/kb/kb_ingest/module.py
# Feladat: Tanítási modul bekötése — repository és storage.
# Sárközi Mihály - 2026.06.07


class KbIngestModule:
    name = "kb.ingest"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_ingest.adapters.NoOpReadingPolicy import NoOpReadingPolicy
        from apps.kb.kb_ingest.bootstrap.service_keys import KB_INGEST_POLICY, KB_INGEST_REPOSITORY
        from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository

        container.register_repository(
            KB_INGEST_REPOSITORY,
            TrainingRepository(container.session_factory),
        )
        container.register_service(KB_INGEST_POLICY, NoOpReadingPolicy())

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbIngestModule"]
