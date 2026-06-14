from __future__ import annotations

from core.kernel.interface.app_keys import module_service_key

KB_INDEXING_JOB_REPOSITORY = module_service_key("kb", "indexing.job_repository")
KB_INDEXED_CHUNK_REPOSITORY = module_service_key("kb", "indexing.indexed_chunk_repository")
KB_INDEXING_DIAGNOSTICS_SERVICE = module_service_key("kb", "indexing.diagnostics_service")

__all__ = [
    "KB_INDEXED_CHUNK_REPOSITORY",
    "KB_INDEXING_DIAGNOSTICS_SERVICE",
    "KB_INDEXING_JOB_REPOSITORY",
]
