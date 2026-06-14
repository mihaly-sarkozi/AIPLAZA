from __future__ import annotations


class KbProcessingModule:
    name = "kb.processing"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_processing.bootstrap.processing_assembly import build_processing_services
        from apps.kb.kb_processing.bootstrap.service_keys import (
            KB_PROCESSING_EVENT_READER,
            KB_PROCESSING_EVENT_REPOSITORY,
            KB_PROCESSING_ISSUE_REPOSITORY,
            KB_PROCESSING_METRICS_REPOSITORY,
            KB_PROCESSING_STATUS_SERVICE,
            KB_PROCESSING_STEP_OUTPUT_ENRICHER,
        )

        services = build_processing_services(session_factory=container.session_factory)
        container.register_repository(KB_PROCESSING_EVENT_REPOSITORY, services.event_repository)
        container.register_repository(KB_PROCESSING_ISSUE_REPOSITORY, services.issue_repository)
        container.register_repository(KB_PROCESSING_METRICS_REPOSITORY, services.metrics_repository)
        container.register_service(KB_PROCESSING_STATUS_SERVICE, services.status_service)
        container.register_service(KB_PROCESSING_EVENT_READER, services.event_reader)
        container.register_service(KB_PROCESSING_STEP_OUTPUT_ENRICHER, services.output_enricher)

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbProcessingModule"]
