from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.billing.runtime import BillingService, PaymentExecutionResult

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_execute_payment_simulated_provider_success(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)
    monkeypatch.setenv("BILLING_PROVIDER", "simulated")

    result = BillingService._execute_payment(  # type: ignore[misc]
        svc,
        amount_cents=1200,
        description="Simulated payment",
        metadata={"flow": "test"},
    )

    assert result.success is True
    assert result.status == "simulated_paid"
    assert result.payment_method == "simulated_card"


def test_execute_payment_stripe_test_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)
    monkeypatch.setenv("BILLING_PROVIDER", "stripe_test")
    monkeypatch.delenv("STRIPE_TEST_SECRET_KEY", raising=False)

    result = BillingService._execute_payment(  # type: ignore[misc]
        svc,
        amount_cents=1200,
        description="Stripe test payment",
        metadata={"flow": "test"},
    )

    assert result.success is False
    assert result.status == "config_error"


def test_execute_payment_default_manual_mode_is_not_auto_paid(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)
    monkeypatch.delenv("BILLING_PROVIDER", raising=False)

    result = BillingService._execute_payment(  # type: ignore[misc]
        svc,
        amount_cents=1200,
        description="Manual payment mode",
        metadata={"flow": "test"},
    )

    assert result.success is False
    assert result.status == "manual_required"
    assert result.payment_method == "manual"


def test_settle_subscription_records_failed_outcome_on_payment_error(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)

    class _Sub:
        plan_code = "starter"
        billing_period = "monthly"

    class _Tenant:
        slug = "demo"

    outcomes: list[str] = []

    monkeypatch.setattr(svc, "ensure_subscription", lambda tenant: _Sub())
    monkeypatch.setattr(svc, "_load_resource_counts", lambda: {})
    monkeypatch.setattr(svc, "_estimate_next_invoice", lambda subscription, resources=None: {"total_cents": 1200})
    monkeypatch.setattr(
        svc,
        "_execute_payment",
        lambda **kwargs: PaymentExecutionResult(
            success=False,
            status="provider_error",
            payment_method="stripe_test_card",
            message="provider down",
        ),
    )

    def _complete(tenant, subscription=None, *, outcome, force=False, force_new_invoice=False):  # type: ignore[no-untyped-def]
        outcomes.append(outcome)
        return type("Response", (), {"status": "payment_failed", "message": "failed"})()

    monkeypatch.setattr(svc, "complete_subscription_billing", _complete)

    result = BillingService.settle_subscription(svc, _Tenant())  # type: ignore[misc]

    assert outcomes == ["failed"]
    assert result.status == "payment_failed"


def test_failed_billing_reuses_previous_grace_and_does_not_update_paid_until(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)
    svc.default_currency = "HUF"

    class _Plan:
        code = "starter"
        name = "Starter"
        price_cents = 1000

    class _Sub:
        tenant_id = 7
        plan_code = "starter"
        billing_period = "monthly"
        scheduled_plan_code = None
        scheduled_billing_period = None
        extra_kb_count = 0
        extra_storage_gb = 0
        carryover_addon_questions = 0
        carryover_training_chars = 0

    class _Tenant:
        tenant_id = 7

    class _Clock:
        @staticmethod
        def now() -> datetime:
            return datetime(2026, 2, 1, 10, 0, tzinfo=UTC)

    class _Invoice:
        status = "payment_failed"
        period_key = "2026-01"
        issued_at = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
        due_at = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)

    captured_due_at: datetime | None = None
    subscription_updated = False

    class _Repo:
        @staticmethod
        def get_invoice(_tenant_id: int, _invoice_type: str, _period_key: str):
            return None

        @staticmethod
        def get_latest_invoice_for_type(_tenant_id: int, invoice_type: str):
            if invoice_type == "monthly_subscription_failed":
                return _Invoice()
            return None

        @staticmethod
        def create_invoice(
            _tenant_id: int,
            *,
            invoice_type: str,
            period_key: str,
            currency: str,
            total_cents: int,
            description: str,
            lines: list[dict[str, object]],
            due_at: datetime,
            status: str,
            issued_at: datetime,
            payment_method: str | None = None,
        ):
            nonlocal captured_due_at
            assert invoice_type == "monthly_subscription_failed"
            assert status == "payment_failed"
            captured_due_at = due_at
            return None

        @staticmethod
        def upsert_subscription(*_args, **_kwargs):
            nonlocal subscription_updated
            subscription_updated = True
            return None

    svc._repo = _Repo()  # type: ignore[attr-defined]
    svc.clock = _Clock()  # type: ignore[attr-defined]

    monkeypatch.setattr(svc, "_current_period", lambda: ("2026-02", None, datetime(2026, 2, 1, 0, 0, tzinfo=UTC), None))
    monkeypatch.setattr(svc, "_billing_due_date", lambda _sub, _fallback: date(2026, 2, 1))
    monkeypatch.setattr(svc, "_subscription_period_key", lambda _billing_date: "2026-02")
    monkeypatch.setattr(svc, "_load_resource_counts", lambda: {})
    monkeypatch.setattr(svc, "_estimate_next_invoice", lambda _sub, _resources: {"total_cents": 1000, "next_extra_storage_gb": 0})
    monkeypatch.setattr(svc, "_plan_map", lambda: {"starter": _Plan(), "free": _Plan()})

    result = BillingService.complete_subscription_billing(  # type: ignore[misc]
        svc,
        _Tenant(),
        subscription=_Sub(),
        outcome="failed",
        force=True,
    )

    assert result.status == "payment_failed"
    assert result.grace_until == "2026-01-15"
    assert captured_due_at is not None
    assert captured_due_at.date().isoformat() == "2026-01-15"
    assert subscription_updated is False
