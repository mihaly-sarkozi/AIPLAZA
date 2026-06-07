from __future__ import annotations

from fastapi import APIRouter, Depends

from core.modules.auth.web.dependencies.auth_dependencies import require_permission

router = APIRouter()


@router.get("/testing/health", dependencies=[Depends(require_permission("kb.admin"))])
async def testing_health() -> dict[str, str]:
    return {"module": "testing", "status": "skeleton"}
