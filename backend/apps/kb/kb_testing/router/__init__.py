from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_testing.router.TestingRouter import router as testing_router

router = APIRouter(prefix="/knowledge", tags=["kb-testing"])
router.include_router(testing_router)

__all__ = ["router"]
