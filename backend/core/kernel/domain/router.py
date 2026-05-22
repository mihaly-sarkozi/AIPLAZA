# backend/core/kernel/domain/router.py
# Feladat: A custom domain HTTP API FastAPI adaptere. Domain overview, custom domain létrehozás, DNS verification és törlés endpointokat köt a DomainService-hez, tenant contexttel és domain.read/domain.write permission ellenőrzéssel. Kernel domain router réteg, amely typed service hibákat HTTP státuszokra mapel.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from core.modules.users.domain.dto import User
from core.kernel.deps.facade import service_dependency
from core.kernel.http.responses import OperationStatusResponse
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.kernel.domain.errors import (
    DomainManagementBlockedError,
    DomainNotFoundError,
    DomainPrimaryDeleteBlockedError,
    DomainTakenError,
    TenantNotFoundError,
)
from core.kernel.domain.errors import DomainDnsVerificationFailedError
from core.kernel.domain.dto import (
    DomainCreateRequest,
    DomainOverviewResponse,
    DomainRecordResponse,
    DomainVerifyRequest,
)
from core.kernel.domain.services import DomainService
from core.kernel.interface.keys import PLATFORM_DOMAIN_SERVICE

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
    except DomainDnsVerificationFailedError as exc:
        raise HTTPException(status_code=400, detail=f"domain_dns_verification_failed:{exc.reason}")


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


@router.post("/platform/domain/custom/delete", response_model=OperationStatusResponse)
def delete_custom_domain(
    tenant: RequiredTenantContextDep,
    body: DomainVerifyRequest = Body(...),
    svc: DomainService = Depends(get_domain_service),
    current_user: User = Depends(require_permission("domain.write")),
):
    try:
        svc.delete_custom_domain(tenant.slug, body.domain)
        return OperationStatusResponse()
    except DomainNotFoundError:
        raise HTTPException(status_code=404, detail="domain_not_found")
    except DomainPrimaryDeleteBlockedError:
        raise HTTPException(status_code=400, detail="domain_primary_delete_blocked")
    except TenantNotFoundError:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    except DomainManagementBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
