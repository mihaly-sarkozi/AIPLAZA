# backend/core/modules/brand/router/brand_router.py
# Feladat: A tenant brand HTTP API FastAPI adaptere. GET és PATCH /platform/brand endpointokat köt a BrandService-hez, kötelező tenant contexttel és brand.read/brand.write permission ellenőrzéssel. Brand router réteg, üzleti logika nélkül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from core.modules.users.domain.dto import User
from core.kernel.deps.facade import service_dependency
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.modules.brand.service.brand_service import BrandService
from core.modules.brand.web.requests.brand_update_request import BrandUpdateRequest
from core.modules.brand.web.responses.brand_response import BrandResponse
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.kernel.interface.keys import PLATFORM_BRAND_SERVICE

get_brand_service = service_dependency(PLATFORM_BRAND_SERVICE)

router = APIRouter()


@router.get("/platform/brand", response_model=BrandResponse)
def get_brand(
    tenant: RequiredTenantContextDep,
    svc: BrandService = Depends(get_brand_service),
    current_user: User = Depends(require_permission("brand.read")),
):
    return svc.get_brand()


@router.patch("/platform/brand", response_model=BrandResponse)
def update_brand(
    tenant: RequiredTenantContextDep,
    body: BrandUpdateRequest = Body(...),
    svc: BrandService = Depends(get_brand_service),
    current_user: User = Depends(require_permission("brand.write")),
):
    return svc.update_brand(body, updated_by=current_user.id)
