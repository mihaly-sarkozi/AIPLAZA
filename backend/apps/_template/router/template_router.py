from __future__ import annotations

from fastapi import APIRouter, Depends

from apps._template.dependencies import get_template_service
from apps._template.service import TemplateService

router = APIRouter()


@router.get("/template/health")
def template_health(service: TemplateService = Depends(get_template_service)) -> dict[str, str]:
    return {"status": service.healthcheck()}
