from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from core.capabilities.users.dto import User
from core.di import RequiredTenantContextDep, service_dependency
from core.platform.auth.auth_dependencies import require_permission
from core.platform.brand.dto import BrandResponse, BrandUpdateRequest
from core.platform.brand.services import BrandService
from core.platform.service_keys import PLATFORM_BRAND_SERVICE

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
