# backend/scaffolding/router.py
# Feladat: Az új app modulok backend router sablonját adja. Egy egyszerű `/template/health` endpointon mutatja meg a module_service_dependency használatát és a TemplateService bekötését. Scaffolding template fájl, amelyből a generátor az új app routerét készíti.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.http.app_dependencies import module_service_dependency
from core.kernel.http.responses import OperationStatus, OperationStatusResponse
from core.kernel.interface.app_keys import module_service_key
from fastapi import APIRouter, Depends

from .service import TemplateService

router = APIRouter()
_get_template_service = module_service_dependency(module_service_key("template"))
_TemplateServiceDep = Depends(_get_template_service)


@router.get("/template/health", response_model=OperationStatusResponse)
def template_health(service: TemplateService = _TemplateServiceDep) -> OperationStatusResponse:
    status = OperationStatus.OK if service.healthcheck() == "ok" else OperationStatus.SUCCESS
    return OperationStatusResponse(status=status)
