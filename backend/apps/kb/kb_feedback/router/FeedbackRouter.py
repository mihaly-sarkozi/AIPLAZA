from __future__ import annotations

from fastapi import APIRouter, Depends

from core.modules.auth.web.dependencies.auth_dependencies import require_permission

router = APIRouter()


@router.get("/feedback/health", dependencies=[Depends(require_permission("kb.train"))])
async def feedback_health() -> dict[str, str]:
    return {"module": "feedback", "status": "skeleton"}
