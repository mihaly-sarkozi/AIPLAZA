from __future__ import annotations

# backend/apps/kb/kb_ingest/bootstrap/dependencies.py
# Feladat: Training service példányok összeállítása (FastAPI Depends).
# Sárközi Mihály - 2026.06.07

from fastapi import Request

from apps.kb.bootstrap.service_keys import KB_FILE_STORAGE
from apps.kb.kb_ingest.bootstrap.service_keys import KB_INGEST_POLICY, KB_INGEST_REPOSITORY
from apps.kb.kb_ingest.service.EstimateFilesService import EstimateFilesService
from apps.kb.kb_ingest.service.ListIngestRunsService import ListIngestRunsService
from apps.kb.kb_ingest.service.TrainingBatchService import TrainingBatchService
from apps.kb.kb_ingest.service.TrainingFileService import TrainingFileService
from apps.kb.kb_ingest.service.TrainingTextService import TrainingTextService
from core.kernel.http.app_dependencies import get_module_repository, get_module_service
from core.modules.auth.web.dependencies.auth_dependencies import require_permission

require_kb_train = require_permission("kb.train")
require_kb_read = require_permission("kb.read")


def get_estimate_files_service(request: Request) -> EstimateFilesService:
    return EstimateFilesService(
        policy=get_module_service(KB_INGEST_POLICY, request),
    )


def get_training_text_service(request: Request) -> TrainingTextService:
    return TrainingTextService(
        repository=get_module_repository(KB_INGEST_REPOSITORY, request),
        file_storage=get_module_repository(KB_FILE_STORAGE, request),
        policy=get_module_service(KB_INGEST_POLICY, request),
    )


def get_training_file_service(request: Request) -> TrainingFileService:
    return TrainingFileService(
        repository=get_module_repository(KB_INGEST_REPOSITORY, request),
        file_storage=get_module_repository(KB_FILE_STORAGE, request),
        policy=get_module_service(KB_INGEST_POLICY, request),
    )


def get_training_batch_service(request: Request) -> TrainingBatchService:
    return TrainingBatchService(
        repository=get_module_repository(KB_INGEST_REPOSITORY, request),
    )


def get_list_ingest_runs_service(request: Request) -> ListIngestRunsService:
    return ListIngestRunsService(repository=get_module_repository(KB_INGEST_REPOSITORY, request))


__all__ = [
    "get_estimate_files_service",
    "get_list_ingest_runs_service",
    "get_training_batch_service",
    "get_training_file_service",
    "get_training_text_service",
    "require_kb_read",
    "require_kb_train",
]
