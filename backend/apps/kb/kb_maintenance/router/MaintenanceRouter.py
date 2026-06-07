from __future__ import annotations

from fastapi import APIRouter, Depends

from core.modules.auth.web.dependencies.auth_dependencies import require_permission

router = APIRouter()


@router.get("/maintenance/health", dependencies=[Depends(require_permission("kb.train"))])
async def maintenance_health() -> dict[str, str]:
    return {"module": "maintenance", "status": "skeleton"}
