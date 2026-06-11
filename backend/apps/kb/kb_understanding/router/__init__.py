from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_understanding.router.UnderstandingRouter import router as understanding_router

router = APIRouter(prefix="/kb", tags=["kb-understanding"])
router.include_router(understanding_router)

__all__ = ["router"]
