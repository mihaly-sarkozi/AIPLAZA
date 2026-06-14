from __future__ import annotations

# backend/apps/kb/kb_crud/module.py
# Feladat: A kb_crud almodul service/repository regisztrációja.
# Sárközi Mihály - 2026.06.07


class KbCrudModule:
    name = "kb.crud"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_crud.adapters.KnowledgeBaseContentCleanup import KnowledgeBaseContentCleanup
        from apps.kb.kb_crud.adapters.LegacyKnowledgeStorageMetrics import LegacyKnowledgeStorageMetrics
        from apps.kb.kb_crud.adapters.LegacyKnowledgeTrainingSummary import LegacyKnowledgeTrainingSummary
        from apps.kb.kb_crud.adapters.PlatformUsageLimit import PlatformUsageLimit
        from apps.kb.kb_crud.adapters.PlatformUserDirectory import PlatformUserDirectory
        from apps.kb.kb_crud.bootstrap.service_keys import (
            KB_CRUD_AUDIT_LOGGER,
            KB_CRUD_CONTENT_CLEANUP,
            KB_CRUD_PERMISSION_REPOSITORY,
            KB_CRUD_REPOSITORY,
            KB_CRUD_STORAGE_METRICS,
            KB_CRUD_TRAINING_SUMMARY,
            KB_CRUD_USAGE_LIMIT,
            KB_CRUD_USER_DIRECTORY,
        )
        from apps.kb.kb_crud.repository.KnowledgeBasePermissionRepository import (
            KnowledgeBasePermissionRepository,
        )
        from apps.kb.kb_crud.repository.KnowledgeBaseRepository import KnowledgeBaseRepository
        from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger

        container.register_repository(
            KB_CRUD_REPOSITORY,
            KnowledgeBaseRepository(container.session_factory),
        )
        container.register_repository(
            KB_CRUD_PERMISSION_REPOSITORY,
            KnowledgeBasePermissionRepository(container.session_factory),
        )
        container.register_repository(
            KB_CRUD_USER_DIRECTORY,
            PlatformUserDirectory(container.user_repository),
        )
        container.register_repository(
            KB_CRUD_CONTENT_CLEANUP,
            KnowledgeBaseContentCleanup(container.session_factory),
        )
        container.register_repository(KB_CRUD_STORAGE_METRICS, LegacyKnowledgeStorageMetrics())
        container.register_repository(KB_CRUD_TRAINING_SUMMARY, LegacyKnowledgeTrainingSummary())
        container.register_repository(KB_CRUD_USAGE_LIMIT, PlatformUsageLimit())
        container.register_repository(
            KB_CRUD_AUDIT_LOGGER,
            KbCrudAuditLogger(container.audit_service),
        )

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbCrudModule"]
