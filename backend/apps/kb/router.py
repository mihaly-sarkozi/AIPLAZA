# backend/apps/kb/router.py
# Feladat: A kb app fő HTTP routere.
# Sárközi Mihály - 2026.06.07
#
# Fokozatos bekötés: jelenleg a kb_crud, kb_ingest és kb_understanding route-ok élnek.
# A többi almodul routere akkor kerül vissza, amikor import-ready.

from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_crud.router import router as crud_router
from apps.kb.kb_ingest.router import router as training_router
from apps.kb.kb_indexing.router import router as indexing_router
from apps.kb.kb_processing.router import router as processing_router
from apps.kb.kb_search.router.SearchRouter import router as search_router
from apps.kb.kb_understanding.router import router as understanding_router

router = APIRouter()
router.include_router(crud_router)
router.include_router(training_router)
router.include_router(understanding_router)
router.include_router(processing_router)
router.include_router(indexing_router)
router.include_router(search_router)

__all__ = ["router"]
