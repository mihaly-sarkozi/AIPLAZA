from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from core.di import RequiredTenantContextDep
from core.platform.auth.auth_dependencies import require_role
from core.capabilities.users.dto import User


def register_debug_billing_routes(
    router: APIRouter,
    *,
    get_billing_service: Callable[..., Any],
    ensure_debug_enabled: Callable[[], None],
    debug_date_request_model: type[Any],
    debug_date_response_model: type[Any],
    debug_run_request_model: type[Any],
    debug_run_response_model: type[Any],
) -> None:
    @router.get("/billing/debug/simulated-date", response_model=debug_date_response_model)
    def get_billing_debug_simulated_date(
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        ensure_debug_enabled()
        return svc.get_debug_simulated_date()

    @router.put("/billing/debug/simulated-date", response_model=debug_date_response_model)
    def set_billing_debug_simulated_date(
        body: debug_date_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        ensure_debug_enabled()
        raw = (body.simulated_date or "").strip()
        if not raw:
            return svc.set_debug_simulated_date(None)
        try:
            parsed = date.fromisoformat(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date") from exc
        return svc.set_debug_simulated_date(parsed)

    @router.delete("/billing/debug/simulated-date", response_model=debug_date_response_model)
    def clear_billing_debug_simulated_date(
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        ensure_debug_enabled()
        return svc.set_debug_simulated_date(None)

    @router.post("/billing/debug/run-subscription-billing", response_model=debug_run_response_model)
    def run_billing_debug_subscription_billing(
        tenant: RequiredTenantContextDep,
        body: debug_run_request_model = Body(...),
        svc: Any = Depends(get_billing_service),
        current_user: User = Depends(require_role("owner")),
    ):
        ensure_debug_enabled()
        try:
            return svc.complete_subscription_billing(
                tenant,
                outcome=body.outcome,
                force=True,
                force_new_invoice=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
