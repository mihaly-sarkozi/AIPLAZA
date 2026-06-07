from __future__ import annotations

from fastapi import APIRouter

from apps.kb.kb_maintenance.router.MaintenanceRouter import router as maintenance_router

router = APIRouter(prefix="/knowledge", tags=["kb-maintenance"])
router.include_router(maintenance_router)

__all__ = ["router"]
