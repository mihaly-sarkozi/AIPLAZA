from __future__ import annotations

# backend/apps/kb/kb_reading/bootstrap/dependencies.py
# Feladat: Service példányok összeállítása kérésenként (FastAPI Depends).
# Sárközi Mihály - 2026.06.07

from fastapi import Request

from apps.kb.kb_reading.bootstrap.service_keys import (
    KB_READING_EVENT_PUBLISHER,
    KB_READING_POLICY,
    KB_READING_REPOSITORY,
    KB_READING_STORAGE,
)
from apps.kb.kb_reading.service.EstimateFilesService import EstimateFilesService
from apps.kb.kb_reading.service.ReadFilesService import ReadFilesService
from apps.kb.kb_reading.service.ReadItemRawService import ReadItemRawService
from apps.kb.kb_reading.service.ReadRunService import ReadRunService
from apps.kb.kb_reading.service.ReadUrlsService import ReadUrlsService
from apps.kb.kb_reading.storage.RawReader import RawReader
from apps.kb.kb_reading.storage.RawWriter import RawWriter
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.kernel.http.app_dependencies import get_module_repository, get_module_service

require_kb_train = require_permission("kb.train")


def _storage(request: Request):
    return get_module_repository(KB_READING_STORAGE, request)


def _repository(request: Request):
    return get_module_repository(KB_READING_REPOSITORY, request)


def get_read_files_service(request: Request) -> ReadFilesService:
    return ReadFilesService(
        repository=_repository(request),
        raw_writer=RawWriter(storage=_storage(request)),
        event_publisher=get_module_service(KB_READING_EVENT_PUBLISHER, request),
    )


def get_read_urls_service(request: Request) -> ReadUrlsService:
    return ReadUrlsService(
        repository=_repository(request),
        raw_writer=RawWriter(storage=_storage(request)),
        event_publisher=get_module_service(KB_READING_EVENT_PUBLISHER, request),
    )


def get_estimate_files_service(request: Request) -> EstimateFilesService:
    return EstimateFilesService(
        policy=get_module_service(KB_READING_POLICY, request),
    )


def get_read_run_service(request: Request) -> ReadRunService:
    return ReadRunService(repository=_repository(request))


def get_read_item_raw_service(request: Request) -> ReadItemRawService:
    storage = _storage(request)
    return ReadItemRawService(
        repository=_repository(request),
        raw_reader=RawReader(storage=storage),
    )


__all__ = [
    "get_estimate_files_service",
    "get_read_files_service",
    "get_read_item_raw_service",
    "get_read_run_service",
    "get_read_urls_service",
    "require_kb_train",
]
