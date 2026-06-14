from __future__ import annotations

from fastapi import Request

from apps.kb.kb_processing.bootstrap.service_keys import KB_PROCESSING_STEP_OUTPUT_ENRICHER
from apps.kb.kb_understanding.bootstrap.service_keys import (
    KB_UNDERSTANDING_CHUNK_REPOSITORY,
    KB_UNDERSTANDING_JOB_REPOSITORY,
)
from apps.kb.kb_understanding.service.RetryUnderstandingService import RetryUnderstandingService
from apps.kb.kb_understanding.service.UnderstandingStatusService import UnderstandingStatusService
from apps.kb.shared.ports.processing_event_reader import NoOpProcessingEventReader
from core.kernel.http.app_dependencies import get_module_repository, get_module_service
from core.kernel.interface.app_keys import module_service_key
from core.modules.auth.web.dependencies.auth_dependencies import require_permission

require_kb_train = require_permission("kb.train")

KB_PROCESSING_EVENT_READER = module_service_key("kb", "processing.event_reader")


def get_understanding_status_service(request: Request) -> UnderstandingStatusService:
    try:
        event_reader = get_module_service(KB_PROCESSING_EVENT_READER, request)
    except Exception:
        event_reader = NoOpProcessingEventReader()
    try:
        output_enricher = get_module_service(KB_PROCESSING_STEP_OUTPUT_ENRICHER, request)
    except Exception:
        output_enricher = None
    return UnderstandingStatusService(
        job_repository=get_module_repository(KB_UNDERSTANDING_JOB_REPOSITORY, request),
        event_reader=event_reader,
        chunk_repository=get_module_repository(KB_UNDERSTANDING_CHUNK_REPOSITORY, request),
        output_enricher=output_enricher,
    )


def get_retry_understanding_service(request: Request) -> RetryUnderstandingService:
    return RetryUnderstandingService(
        job_repository=get_module_repository(KB_UNDERSTANDING_JOB_REPOSITORY, request),
    )


__all__ = [
    "get_retry_understanding_service",
    "get_understanding_status_service",
    "require_kb_train",
]
