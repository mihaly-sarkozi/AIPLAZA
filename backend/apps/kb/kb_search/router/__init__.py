from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_search.router.SearchRouter import router as search_router

router = APIRouter(prefix="/knowledge", tags=["kb-search"])
router.include_router(search_router)

__all__ = ["router"]
