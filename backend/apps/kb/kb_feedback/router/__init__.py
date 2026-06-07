from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_feedback.router.FeedbackRouter import router as feedback_router

router = APIRouter(prefix="/knowledge", tags=["kb-feedback"])
router.include_router(feedback_router)

__all__ = ["router"]
