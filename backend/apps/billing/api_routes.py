# backend/apps/billing/api_routes.py
# Feladat: A billing app fő FastAPI endpointjait regisztrálja. Owner-only előfizetés, upgrade, addon, settlement és invoice PDF műveleteket köt a BillingService-hez, az access-status endpointot pedig bejelentkezett usernek adja. Program-specifikus HTTP adapter rate limittel és tenant/auth védelemmel.
# Sárközi Mihály - 2026.05.21

import json
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from core.modules.users.domain.dto import User
from core.kernel.http.tenant_dependencies import RequestTenantContext, require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user, require_permission, require_role


def register_billing_routes(
    router: APIRouter,
    *,
    get_billing_service: Callable[..., Any],
    overview_response_model: type[Any],
    access_status_response_model: type[Any],
    subscription_update_request_model: type[Any],
    cancellation_request_model: type[Any],
    cancellation_response_model: type[Any],
    upgrade_preview_response_model: type[Any],
    upgrade_complete_response_model: type[Any],
    addon_purchase_request_model: type[Any],
    invoice_response_model: type[Any],
    debug_billing_run_response_model: type[Any],
) -> None:
    @router.get("/billing/overview", response_model=overview_response_model)
    @limiter.limit("30/minute")
    def get_billing_overview(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_permission("billing.read")),
    ):
        return svc.get_overview(tenant)

    @router.get("/billing/access-status", response_model=access_status_response_model)
    @limiter.limit("60/minute")
    def get_billing_access_status(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(get_current_user),
    ):
        return svc.get_access_status(tenant)

    @router.patch("/billing/subscription")
    @limiter.limit("10/minute")
    def update_billing_subscription(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        body: subscription_update_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.update_subscription(tenant, plan_code=body.plan_code, billing_period=body.billing_period)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/subscription/cancel", response_model=cancellation_response_model)
    @limiter.limit("5/minute")
    def cancel_billing_subscription(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        body: cancellation_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.cancel_subscription(
                tenant,
                reason_code=body.reason_code,
                reason_text=body.reason_text,
                requested_by_user_id=current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/subscription/delete-access", response_model=cancellation_response_model)
    @limiter.limit("5/minute")
    def delete_billing_service_access(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.delete_service_access(
                tenant,
                requested_by_user_id=current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/subscription/restore-renewal", response_model=cancellation_response_model)
    @limiter.limit("5/minute")
    def restore_billing_subscription_renewal(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.restore_subscription_renewal(
                tenant,
                requested_by_user_id=current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/billing/subscription/upgrade-preview", response_model=upgrade_preview_response_model)
    @limiter.limit("20/minute")
    def billing_upgrade_preview(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
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
    @limiter.limit("10/minute")
    def billing_upgrade_complete(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        body: subscription_update_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.complete_upgrade_after_checkout(tenant, plan_code=body.plan_code, billing_period=body.billing_period)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/webhooks/{provider}")
    @limiter.limit("60/minute")
    async def billing_payment_webhook(
        request: Request,
        provider: str,
        svc: Any = Depends(get_billing_service),
    ):
        payload_bytes = await request.body()
        signature = request.headers.get("Stripe-Signature") or request.headers.get("X-Billing-Signature")
        secret_key = f"BILLING_{provider.upper()}_WEBHOOK_SECRET"
        if not svc.verify_payment_webhook_signature(
            payload=payload_bytes,
            signature=signature,
            secret=os.getenv(secret_key),
        ):
            raise HTTPException(status_code=401, detail="Invalid billing webhook signature")
        try:
            payload = json.loads(payload_bytes.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc
        event_id = str(payload.get("id") or payload.get("event_id") or "")
        event_type = str(payload.get("type") or payload.get("event_type") or "")
        try:
            return svc.process_verified_payment_event(
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/addons/purchase", response_model=invoice_response_model)
    @limiter.limit("10/minute")
    def purchase_billing_addon(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        body: addon_purchase_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.purchase_addon(tenant, addon_code=body.addon_code, quantity=body.quantity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/billing/subscription/settle", response_model=debug_billing_run_response_model)
    @limiter.limit("5/minute")
    def settle_billing_subscription(
        request: Request,
        tenant: RequestTenantContext = Depends(require_tenant_context),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        try:
            return svc.settle_subscription(tenant)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/billing/invoices/{invoice_id}/pdf")
    @limiter.limit("30/minute")
    def download_billing_invoice_pdf(
        request: Request,
        invoice_id: int,
        tenant: RequestTenantContext = Depends(require_tenant_context),
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
