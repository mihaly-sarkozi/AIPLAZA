# backend/apps/billing/router.py
# Feladat: A billing app FastAPI router kompozíciós pontja. Összeköti a production billing route-okat és a környezeti kapcsolóval védett debug route-okat, majd a platform tenant usage service dependencyt használja. Program-specifikus HTTP router belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from apps.billing.api_routes import register_billing_routes
from apps.billing.debug_routes import register_debug_billing_routes
from apps.billing.schemas import (
    BillingAccessStatusResponse,
    BillingAddonPurchaseRequest,
    BillingDebugBillingRunRequest,
    BillingDebugBillingRunResponse,
    BillingDebugDateRequest,
    BillingDebugDateResponse,
    BillingInvoiceResponse,
    BillingOverviewResponse,
    BillingSubscriptionUpdateRequest,
    BillingUpgradeCompleteResponse,
    BillingUpgradePreviewResponse,
)
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.deps.facade import service_dependency
from core.kernel.config.environment import normalize_app_env
from core.kernel.interface.observability import log_structured_event

get_billing_service = service_dependency(PLATFORM_TENANT_USAGE_SERVICE)
router = APIRouter()


def _ensure_billing_debug_enabled() -> None:
    env = normalize_app_env(os.getenv("APP_ENV", "local"))
    if env not in {"local", "staging"}:
        raise HTTPException(status_code=404, detail="Not found")
    enabled = (os.getenv("BILLING_DEBUG_ROUTES_ENABLED") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=404, detail="Not found")


def _audit_billing_debug_action(action: str, *, request=None, current_user=None, tenant=None) -> None:
    log_structured_event(
        "apps.billing.debug",
        "billing_debug_route.used",
        action=action,
        env=normalize_app_env(os.getenv("APP_ENV", "local")),
        user_id=getattr(current_user, "id", None),
        tenant_id=getattr(tenant, "tenant_id", None),
        path=str(getattr(getattr(request, "url", None), "path", "") or ""),
    )


register_billing_routes(
    router,
    get_billing_service=get_billing_service,
    overview_response_model=BillingOverviewResponse,
    access_status_response_model=BillingAccessStatusResponse,
    subscription_update_request_model=BillingSubscriptionUpdateRequest,
    upgrade_preview_response_model=BillingUpgradePreviewResponse,
    upgrade_complete_response_model=BillingUpgradeCompleteResponse,
    addon_purchase_request_model=BillingAddonPurchaseRequest,
    invoice_response_model=BillingInvoiceResponse,
    debug_billing_run_response_model=BillingDebugBillingRunResponse,
)

register_debug_billing_routes(
    router,
    get_billing_service=get_billing_service,
    ensure_debug_enabled=_ensure_billing_debug_enabled,
    audit_debug_action=_audit_billing_debug_action,
    debug_date_request_model=BillingDebugDateRequest,
    debug_date_response_model=BillingDebugDateResponse,
    debug_run_request_model=BillingDebugBillingRunRequest,
    debug_run_response_model=BillingDebugBillingRunResponse,
)


__all__ = ["get_billing_service", "router"]
