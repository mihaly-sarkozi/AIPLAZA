# backend/core/modules/tenant/dependencies.py
# Feladat: FastAPI dependency helper réteg a tenant modulhoz. Az aktuális tenant request contextet és tenant service-eket adja tovább route handlerek számára. HTTP integrációs contract a tenant-aware endpointokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import Request

from core.kernel.app.app_container import container
from core.modules.tenant.service import TenantSignupService


def get_tenant_signup_service(request: Request) -> TenantSignupService:
    return container.build_tenant_signup_service_for_request(request)

__all__ = ["get_tenant_signup_service"]
