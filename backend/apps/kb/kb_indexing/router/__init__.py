from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_indexing.router.IndexingDiagnosticsRouter import router as diagnostics_router

router = APIRouter(prefix="/kb", tags=["kb-indexing"])
router.include_router(diagnostics_router)

__all__ = ["router"]
