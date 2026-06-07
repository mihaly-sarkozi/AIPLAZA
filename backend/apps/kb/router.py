# backend/apps/kb/router.py
# Feladat: A kb app fő HTTP routere.
# Sárközi Mihály - 2026.06.07
#
# Fokozatos bekötés: jelenleg csak a kb_training route-ok élnek (szöveges tanítás teszt).
# A többi almodul routere akkor kerül vissza, amikor import-ready.

from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_training.router import router as training_router

router = APIRouter()
router.include_router(training_router)

__all__ = ["router"]
