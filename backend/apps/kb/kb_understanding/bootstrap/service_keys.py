from __future__ import annotations

# backend/apps/kb/kb_understanding/bootstrap/service_keys.py
# Feladat: Megértési modul DI service kulcsok.
# Kulcs-konvenció: module_service_key("kb", "understanding.<komponens>").
# Sárközi Mihály - 2026.06.11

from core.kernel.interface.app_keys import module_service_key

KB_UNDERSTANDING_JOB_REPOSITORY = module_service_key("kb", "understanding.job_repository")
KB_UNDERSTANDING_CHUNK_REPOSITORY = module_service_key("kb", "understanding.chunk_repository")
KB_UNDERSTANDING_PIPELINE = module_service_key("kb", "understanding.pipeline")
KB_UNDERSTANDING_START_SERVICE = module_service_key("kb", "understanding.start_service")

__all__ = [
    "KB_UNDERSTANDING_CHUNK_REPOSITORY",
    "KB_UNDERSTANDING_JOB_REPOSITORY",
    "KB_UNDERSTANDING_PIPELINE",
    "KB_UNDERSTANDING_START_SERVICE",
]
