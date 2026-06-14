from __future__ import annotations

from core.kernel.interface.app_keys import module_service_key

KB_PROCESSING_EVENT_REPOSITORY = module_service_key("kb", "processing.event_repository")
KB_PROCESSING_ISSUE_REPOSITORY = module_service_key("kb", "processing.issue_repository")
KB_PROCESSING_METRICS_REPOSITORY = module_service_key("kb", "processing.metrics_repository")
KB_PROCESSING_STATUS_SERVICE = module_service_key("kb", "processing.status_service")
KB_PROCESSING_EVENT_READER = module_service_key("kb", "processing.event_reader")
KB_PROCESSING_STEP_OUTPUT_ENRICHER = module_service_key("kb", "processing.step_output_enricher")

__all__ = [
    "KB_PROCESSING_EVENT_REPOSITORY",
    "KB_PROCESSING_EVENT_READER",
    "KB_PROCESSING_ISSUE_REPOSITORY",
    "KB_PROCESSING_METRICS_REPOSITORY",
    "KB_PROCESSING_STATUS_SERVICE",
    "KB_PROCESSING_STEP_OUTPUT_ENRICHER",
]
