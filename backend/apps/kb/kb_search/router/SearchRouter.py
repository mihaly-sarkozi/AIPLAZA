from __future__ import annotations

from fastapi import APIRouter, Depends

from core.modules.auth.web.dependencies.auth_dependencies import require_permission

router = APIRouter()


@router.get("/search/health", dependencies=[Depends(require_permission("kb.read"))])
async def search_health() -> dict[str, str]:
    return {"module": "search", "status": "skeleton"}
