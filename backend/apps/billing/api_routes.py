from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from core.capabilities.users.dto import User
from core.di import RequiredTenantContextDep
from core.platform.auth.auth_dependencies import get_current_user, require_role


def register_billing_routes(
    router: APIRouter,
    *,
    get_billing_service: Callable[..., Any],
    overview_response_model: type[Any],
    access_status_response_model: type[Any],
    subscription_update_request_model: type[Any],
    upgrade_preview_response_model: type[Any],
    upgrade_complete_response_model: type[Any],
    addon_purchase_request_model: type[Any],
    invoice_response_model: type[Any],
    debug_billing_run_response_model: type[Any],
) -> None:
    @router.get("/billing/overview", response_model=overview_response_model)
    def get_billing_overview(
        tenant: RequiredTenantContextDep,
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        return svc.get_overview(tenant)

    @router.get("/billing/access-status", response_model=access_status_response_model)
    def get_billing_access_status(
        tenant: RequiredTenantContextDep,
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(get_current_user),
    ):
        return svc.get_access_status(tenant)

    @router.patch("/billing/subscription")
    def update_billing_subscription(
        tenant: RequiredTenantContextDep,
        body: subscription_update_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.update_subscription(tenant, plan_code=body.plan_code, billing_period=body.billing_period)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/billing/subscription/upgrade-preview", response_model=upgrade_preview_response_model)
    def billing_upgrade_preview(
        tenant: RequiredTenantContextDep,
        plan_code: str = Query(..., alias="plan_code"),
        billing_period: str = Query("monthly"),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.get_upgrade_preview(tenant, plan_code=plan_code, billing_period=billing_period)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/subscription/upgrade-complete", response_model=upgrade_complete_response_model)
    def billing_upgrade_complete(
        tenant: RequiredTenantContextDep,
        body: subscription_update_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.complete_upgrade_after_checkout(tenant, plan_code=body.plan_code, billing_period=body.billing_period)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/addons/purchase", response_model=invoice_response_model)
    def purchase_billing_addon(
        tenant: RequiredTenantContextDep,
        body: addon_purchase_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.purchase_addon(tenant, addon_code=body.addon_code, quantity=body.quantity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/subscription/settle", response_model=debug_billing_run_response_model)
    def settle_billing_subscription(
        tenant: RequiredTenantContextDep,
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.settle_subscription(tenant)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/billing/invoices/{invoice_id}/pdf")
    def download_billing_invoice_pdf(
        invoice_id: int,
        tenant: RequiredTenantContextDep,
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            content, filename = svc.render_invoice_pdf(tenant, invoice_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
