from __future__ import annotations

# backend/apps/kb/kb_reading/module.py
# Feladat: A beolvasás modul bekötése: útvonalak és szolgáltatások regisztrálása.
# Sárközi Mihály - 2026.06.07


class KbReadingModule:
    """A beolvasás modul regisztrációs pontja."""
    name = "kb.reading"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_reading.adapters import (
            NoOpReadingEventPublisher,
            NoOpReadingPolicy,
            ObjectStorageReadingStorage,
        )
        from apps.kb.kb_reading.bootstrap.service_keys import (
            KB_READING_EVENT_PUBLISHER,
            KB_READING_POLICY,
            KB_READING_REPOSITORY,
            KB_READING_STORAGE,
        )
        from apps.kb.kb_reading.repository.ReadingRepository import ReadingRepository
        from shared.object_storage import get_object_storage

        container.register_repository(
            KB_READING_REPOSITORY,
            ReadingRepository(container.session_factory),
        )
        container.register_repository(
            KB_READING_STORAGE,
            ObjectStorageReadingStorage(get_object_storage()),
        )
        container.register_service(KB_READING_POLICY, NoOpReadingPolicy())
        container.register_service(KB_READING_EVENT_PUBLISHER, NoOpReadingEventPublisher())

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbReadingModule"]
