# backend/tests/unit/test_billing_api_contracts.py
# Feladat: A billing app HTTP contractjainak és biztonsági peremfeltételeinek unit tesztjei. Request validációt, route rate limit dekorátorok jelenlétét és debug route környezeti védelmét ellenőrzi. Billing API regressziós teszt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from apps.billing.router import _ensure_billing_debug_enabled, router
from apps.billing.schemas import (
    BillingAddonPurchaseRequest,
    BillingCancellationRequest,
    BillingDebugBillingRunRequest,
    BillingSubscriptionUpdateRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_billing_subscription_update_request_normalizes_and_validates() -> None:
    request = BillingSubscriptionUpdateRequest(plan_code="Starter", billing_period="QUARTERLY")

    assert request.plan_code == "starter"
    assert request.billing_period == "quarterly"

    with pytest.raises(ValidationError):
        BillingSubscriptionUpdateRequest(plan_code="starter", billing_period="weekly")


def test_billing_addon_purchase_request_limits_quantity() -> None:
    request = BillingAddonPurchaseRequest(addon_code="Question_Pack_100", quantity=2)

    assert request.addon_code == "question_pack_100"
    assert request.quantity == 2

    with pytest.raises(ValidationError):
        BillingAddonPurchaseRequest(addon_code="question_pack_100", quantity=0)

    with pytest.raises(ValidationError):
        BillingAddonPurchaseRequest(addon_code="question_pack_100", quantity=101)


def test_billing_cancellation_request_accepts_known_reasons() -> None:
    request = BillingCancellationRequest(reason_code="TOO_EXPENSIVE", reason_text="  túl drága  ")

    assert request.reason_code == "too_expensive"
    assert request.reason_text == "túl drága"

    with pytest.raises(ValidationError):
        BillingCancellationRequest(reason_code="invalid", reason_text="")


def test_billing_debug_run_request_accepts_only_known_outcomes() -> None:
    request = BillingDebugBillingRunRequest(outcome="SUCCESS")

    assert request.outcome == "success"

    with pytest.raises(ValidationError):
        BillingDebugBillingRunRequest(outcome="retry")


def test_billing_routes_have_rate_limit_contracts() -> None:
    billing_route_limits: dict[str, set[str]] = {}
    for route in router.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/billing"):
            continue
        endpoint = getattr(route, "endpoint")
        billing_route_limits.setdefault(path, set()).update(
            str(limit.limit) for limit in getattr(endpoint, "__limits__", [])
        )

    expected_limits = {
        "/billing/overview": "30/minute",
        "/billing/access-status": "60/minute",
        "/billing/subscription": "10/minute",
        "/billing/subscription/cancel": "5/minute",
        "/billing/subscription/delete-access": "5/minute",
        "/billing/subscription/restore-renewal": "5/minute",
        "/billing/subscription/upgrade-preview": "20/minute",
        "/billing/subscription/upgrade-complete": "10/minute",
        "/billing/webhooks/{provider}": "60/minute",
        "/billing/addons/purchase": "10/minute",
        "/billing/subscription/settle": "5/minute",
        "/billing/invoices/{invoice_id}/pdf": "30/minute",
        "/billing/debug/run-subscription-billing": "3/minute",
    }

    for path, expected in expected_limits.items():
        limit_values = billing_route_limits[path]
        if isinstance(expected, set):
            assert expected.issubset(limit_values)
        else:
            assert expected in limit_values


def test_billing_tenant_dependency_is_not_exposed_as_query_param() -> None:
    tenant_scoped_paths = {
        "/billing/overview",
        "/billing/access-status",
        "/billing/subscription",
        "/billing/subscription/cancel",
        "/billing/subscription/delete-access",
        "/billing/subscription/restore-renewal",
        "/billing/subscription/upgrade-preview",
        "/billing/subscription/upgrade-complete",
        "/billing/addons/purchase",
        "/billing/subscription/settle",
        "/billing/invoices/{invoice_id}/pdf",
        "/billing/debug/run-subscription-billing",
    }

    for route in router.routes:
        if getattr(route, "path", "") not in tenant_scoped_paths:
            continue
        query_param_names = {
            getattr(param, "name", "")
            for param in (getattr(getattr(route, "dependant", None), "query_params", []) or [])
        }
        assert "tenant" not in query_param_names


def test_billing_debug_routes_hidden_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("BILLING_DEBUG_ROUTES_ENABLED", "true")

    with pytest.raises(HTTPException) as exc:
        _ensure_billing_debug_enabled()

    assert exc.value.status_code == 404


def test_billing_debug_routes_require_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("BILLING_DEBUG_ROUTES_ENABLED", raising=False)

    with pytest.raises(HTTPException) as exc:
        _ensure_billing_debug_enabled()

    assert exc.value.status_code == 404

    monkeypatch.setenv("BILLING_DEBUG_ROUTES_ENABLED", "1")
    _ensure_billing_debug_enabled()
