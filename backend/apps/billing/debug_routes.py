# backend/apps/billing/debug_routes.py
# Feladat: Nem production billing debug endpointokat regisztrál dátumszimulációhoz és kézi előfizetés-billing futtatáshoz. Minden route owner jogosultságot, környezeti debug kapcsolót és rate limitet használ, prod környezetben 404-et ad. Program-specifikus fejlesztői HTTP adapter.
# Sárközi Mihály - 2026.05.21

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core.kernel.http.tenant_dependencies import RequestTenantContext, require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_role
from core.modules.users.domain.dto import User


def register_debug_billing_routes(
    router: APIRouter,
    *,
    get_billing_service: Callable[..., Any],
    ensure_debug_enabled: Callable[[], None],
    audit_debug_action: Callable[..., None],
    debug_run_request_model: type[Any],
    debug_run_response_model: type[Any],
) -> None:
    @router.post("/billing/debug/run-subscription-billing", response_model=debug_run_response_model)
    @limiter.limit("3/minute")
    def run_billing_debug_subscription_billing(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        body: debug_run_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        ensure_debug_enabled()
        audit_debug_action("run_subscription_billing", request=request, current_user=current_user, tenant=tenant)
        try:
            return svc.complete_subscription_billing(
                tenant,
                outcome=body.outcome,
                force=True,
                force_new_invoice=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
