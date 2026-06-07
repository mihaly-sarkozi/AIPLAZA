from __future__ import annotations

# backend/apps/kb/kb_reading/router/__init__.py
# Feladat: Útválasztó összeállítása és előtag.
# Sárközi Mihály - 2026.06.07

from fastapi import APIRouter

from apps.kb.kb_reading.router.ReadingRouter import router as reading_router

router = APIRouter(prefix="/kb", tags=["kb-reading"])
router.include_router(reading_router)

__all__ = ["router"]
