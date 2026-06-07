from __future__ import annotations

# backend/apps/kb/kb_training/module.py
# Feladat: Tanítási modul bekötése — repository és storage.
# Sárközi Mihály - 2026.06.07


class KbTrainingModule:
    name = "kb.training"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_training.bootstrap.service_keys import (
            KB_TRAINING_REPOSITORY,
            KB_TRAINING_STORAGE,
        )
        from apps.kb.kb_training.repository.TrainingRepository import TrainingRepository
        from shared.object_storage import get_object_storage

        container.register_repository(
            KB_TRAINING_REPOSITORY,
            TrainingRepository(container.session_factory),
        )
        container.register_repository(KB_TRAINING_STORAGE, get_object_storage())

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbTrainingModule"]
