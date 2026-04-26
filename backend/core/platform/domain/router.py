from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from core.capabilities.users.dto import User
from core.di import RequiredTenantContextDep, service_dependency
from core.platform.auth.auth_dependencies import require_permission
from core.platform.domain.errors import DomainManagementBlockedError, DomainNotFoundError, DomainTakenError, TenantNotFoundError
from core.platform.domain.dto import (
    DomainCreateRequest,
    DomainOverviewResponse,
    DomainRecordResponse,
    DomainVerifyRequest,
)
from core.platform.domain.services import DomainService
from core.platform.service_keys import PLATFORM_DOMAIN_SERVICE

get_domain_service = service_dependency(PLATFORM_DOMAIN_SERVICE)

router = APIRouter()


@router.get("/platform/domain", response_model=DomainOverviewResponse)
def get_domain_overview(
    tenant: RequiredTenantContextDep,
    svc: DomainService = Depends(get_domain_service),
    current_user: User = Depends(require_permission("domain.read")),
):
    return svc.get_overview(tenant.slug, tenant.domain)


@router.post("/platform/domain/custom", response_model=DomainRecordResponse)
def add_custom_domain(
    tenant: RequiredTenantContextDep,
    body: DomainCreateRequest = Body(...),
    svc: DomainService = Depends(get_domain_service),
    current_user: User = Depends(require_permission("domain.write")),
):
    try:
        return svc.add_custom_domain(
            tenant.slug,
            body.domain,
            actor_user_id=current_user.id,
        )
    except DomainTakenError:
        raise HTTPException(status_code=409, detail="domain_taken")
    except TenantNotFoundError:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    except DomainManagementBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/platform/domain/custom/verify", response_model=DomainRecordResponse)
def verify_custom_domain(
    tenant: RequiredTenantContextDep,
    body: DomainVerifyRequest = Body(...),
    svc: DomainService = Depends(get_domain_service),
    current_user: User = Depends(require_permission("domain.write")),
):
    try:
        return svc.verify_custom_domain(
            tenant.slug,
            body.domain,
            actor_user_id=current_user.id,
        )
    except DomainNotFoundError:
        raise HTTPException(status_code=404, detail="domain_not_found")
    except TenantNotFoundError:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    except DomainManagementBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
