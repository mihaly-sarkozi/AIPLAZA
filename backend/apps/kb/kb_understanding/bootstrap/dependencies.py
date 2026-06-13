from __future__ import annotations

from fastapi import Request

from apps.kb.kb_understanding.bootstrap.service_keys import (
    KB_UNDERSTANDING_CHUNK_REPOSITORY,
    KB_UNDERSTANDING_JOB_REPOSITORY,
    KB_UNDERSTANDING_STEP_RUN_REPOSITORY,
)
from apps.kb.kb_understanding.service.RetryUnderstandingService import RetryUnderstandingService
from apps.kb.kb_understanding.service.UnderstandingStatusService import UnderstandingStatusService
from core.kernel.http.app_dependencies import get_module_repository
from core.modules.auth.web.dependencies.auth_dependencies import require_permission

require_kb_train = require_permission("kb.train")


def get_understanding_status_service(request: Request) -> UnderstandingStatusService:
    return UnderstandingStatusService(
        job_repository=get_module_repository(KB_UNDERSTANDING_JOB_REPOSITORY, request),
        step_run_repository=get_module_repository(KB_UNDERSTANDING_STEP_RUN_REPOSITORY, request),
        chunk_repository=get_module_repository(KB_UNDERSTANDING_CHUNK_REPOSITORY, request),
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
