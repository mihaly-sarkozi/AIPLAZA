# Ez a fájl a függőség-injektálási belépési pontokat és helper függvényeket tartalmazza.
from __future__ import annotations

from fastapi import Request

from core.kernel.bootstrap.container import container
from core.extensions.tenant.service import TenantSignupService


def get_tenant_signup_service(request: Request) -> TenantSignupService:
    return container.build_tenant_signup_service_for_request(request)

__all__ = ["get_tenant_signup_service"]
