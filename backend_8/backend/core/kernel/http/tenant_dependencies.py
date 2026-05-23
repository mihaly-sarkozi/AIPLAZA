# backend/core/kernel/http/tenant_dependencies.py
# Feladat: FastAPI dependency-ket ad opcionális és kötelező tenant context használatához. A TenantMiddleware által request.state-re tett snapshotból épít RequestTenantContextet, és fallbackként helyreállítja a tenant contextvart is. Core HTTP adapter, amelyet core és app routerek használnak tenant-aware endpointokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from core.modules.tenant.context.request_tenant_context import (
    RequestTenantContext,
    build_request_tenant_context,
    validate_required_tenant_context,
)
from core.modules.tenant.context.tenant_context import current_tenant_schema


def _restore_tenant_context_fallback(slug: str | None) -> None:
    if slug:
        current_tenant_schema.set(slug)


def get_tenant_context(request: Request) -> RequestTenantContext:
    snapshot = getattr(request.state, "tenant_snapshot", None)
    slug = getattr(snapshot, "slug", None) or getattr(request.state, "tenant_slug", None)
    _restore_tenant_context_fallback(slug)
    return build_request_tenant_context(snapshot=snapshot, request_state=request.state)


def require_tenant_context(
    tenant: RequestTenantContext = Depends(get_tenant_context),
) -> RequestTenantContext:
    ok, _reason = validate_required_tenant_context(tenant)
    if not ok:
        raise HTTPException(status_code=400, detail="Tenant required.")
    return tenant


def set_tenant_context_from_request(request: Request) -> None:
    get_tenant_context(request)


OptionalTenantContextDep = Annotated[RequestTenantContext, Depends(get_tenant_context)]
RequiredTenantContextDep = Annotated[RequestTenantContext, Depends(require_tenant_context)]


__all__ = [
    "OptionalTenantContextDep",
    "RequestTenantContext",
    "RequiredTenantContextDep",
    "get_tenant_context",
    "require_tenant_context",
    "set_tenant_context_from_request",
]
