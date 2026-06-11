from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_ingest.router.TrainingRouter import router as training_router

router = APIRouter(prefix="/kb", tags=["kb-training"])
router.include_router(training_router)

__all__ = ["router"]
