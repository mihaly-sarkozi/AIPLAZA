from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_processing.router.ProcessingStatusRouter import router as processing_status_router

router = APIRouter(prefix="/kb", tags=["kb-processing"])
router.include_router(processing_status_router)

__all__ = ["router"]
