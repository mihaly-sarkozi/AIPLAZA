from __future__ import annotations

# backend/apps/kb/kb_training/bootstrap/dependencies.py
# Feladat: Training service példányok összeállítása (FastAPI Depends).
# Sárközi Mihály - 2026.06.07

from fastapi import Request

from apps.kb.kb_training.bootstrap.service_keys import (
    KB_TRAINING_REPOSITORY,
    KB_TRAINING_STORAGE,
)
from apps.kb.kb_training.service.TrainingBatchService import TrainingBatchService
from apps.kb.kb_training.service.TrainingTextService import TrainingTextService
from apps.kb.kb_training.storage.TrainingRawWriter import TrainingRawWriter
from core.kernel.http.app_dependencies import get_module_repository
from core.modules.auth.web.dependencies.auth_dependencies import require_permission

require_kb_train = require_permission("kb.train")


def get_training_text_service(request: Request) -> TrainingTextService:
    storage = get_module_repository(KB_TRAINING_STORAGE, request)
    return TrainingTextService(
        repository=get_module_repository(KB_TRAINING_REPOSITORY, request),
        raw_writer=TrainingRawWriter(storage=storage),
    )


def get_training_batch_service(request: Request) -> TrainingBatchService:
    return TrainingBatchService(
        repository=get_module_repository(KB_TRAINING_REPOSITORY, request),
    )


__all__ = [
    "get_training_batch_service",
    "get_training_text_service",
    "require_kb_train",
]
