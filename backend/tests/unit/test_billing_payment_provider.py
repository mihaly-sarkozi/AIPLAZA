from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.billing.payment import PaymentExecutionResult
from apps.billing.service import BillingService

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
    assert result.grace_until == "2026-01-22"
    assert captured_due_at is not None
    assert captured_due_at.date().isoformat() == "2026-01-15"
    assert subscription_updated is False


def test_cancel_subscription_does_not_require_knowledge_base_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)

    class _Tenant:
        tenant_id = 7
        slug = "demo"

    class _Sub:
        pass

    class _CancellationRow:
        id = 123

    created_payload: dict[str, object] = {}

    class _Repo:
        @staticmethod
        def create_cancellation_request(**kwargs):
            created_payload.update(kwargs)
            return _CancellationRow()

    svc._repo = _Repo()  # type: ignore[attr-defined]
    monkeypatch.setattr(svc, "ensure_subscription", lambda _tenant: _Sub())
    monkeypatch.setattr(svc, "_load_resource_counts", lambda: {"knowledge_bases": 2})
    monkeypatch.setattr(svc, "_current_period", lambda: ("2026-05", None, datetime(2026, 5, 31, tzinfo=UTC), None))
    monkeypatch.setattr(svc, "_subscription_due_date", lambda _tenant_id, _subscription, _fallback: date(2026, 5, 31))

    result = BillingService.cancel_subscription(  # type: ignore[misc]
        svc,
        _Tenant(),
        reason_code="too_expensive",
        reason_text="",
        requested_by_user_id=11,
    )

    assert result.status == "deactivation_requested"
    assert result.active_kb_count == 2
    assert result.cancellation_request_id == 123
    assert created_payload["active_kb_count"] == 2


def test_cancel_subscription_records_request_without_immediate_deactivation(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)

    class _Tenant:
        tenant_id = 7
        slug = "demo"

    class _Sub:
        pass

    class _Clock:
        @staticmethod
        def now() -> datetime:
            return datetime(2026, 5, 28, 12, 0, tzinfo=UTC)

    class _CancellationRow:
        id = 123

    created_payload: dict[str, object] = {}
    class _Repo:
        @staticmethod
        def create_cancellation_request(**kwargs):
            created_payload.update(kwargs)
            return _CancellationRow()

    svc._repo = _Repo()  # type: ignore[attr-defined]
    svc.clock = _Clock()  # type: ignore[attr-defined]
    monkeypatch.setattr(svc, "ensure_subscription", lambda _tenant: _Sub())
    monkeypatch.setattr(svc, "_load_resource_counts", lambda: {"knowledge_bases": 0})
    monkeypatch.setattr(svc, "_current_period", lambda: ("2026-05", None, datetime(2026, 5, 31, tzinfo=UTC), None))
    monkeypatch.setattr(svc, "_subscription_due_date", lambda _tenant_id, _subscription, _fallback: date(2026, 5, 31))

    result = BillingService.cancel_subscription(  # type: ignore[misc]
        svc,
        _Tenant(),
        reason_code="not_using",
        reason_text=" nem használjuk ",
        requested_by_user_id=11,
    )

    assert result.status == "deactivation_requested"
    assert "kijelentkeztet" not in result.message.lower()
    assert result.cancellation_request_id == 123
    assert created_payload["tenant_id"] == 7
    assert created_payload["tenant_slug"] == "demo"
    assert created_payload["reason_code"] == "not_using"
    assert created_payload["reason_text"] == "nem használjuk"
    assert created_payload["active_kb_count"] == 0
    assert created_payload["deactivated_at"] is None
    assert created_payload["effective_at"] == datetime(2026, 6, 1, 0, 0, tzinfo=UTC)


def test_delete_service_access_deactivates_tenant_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)

    class _Tenant:
        tenant_id = 7
        slug = "demo"

    class _Sub:
        pass

    class _Clock:
        @staticmethod
        def now() -> datetime:
            return datetime(2026, 5, 30, 8, 0, tzinfo=UTC)

    class _Cancellation:
        id = 123
        status = "deactivation_requested"
        deactivated_at = None

    marked_deactivated: list[tuple[int, datetime]] = []
    deactivated_tenants: list[int] = []

    class _Repo:
        @staticmethod
        def get_latest_cancellation_request(_tenant_id: int):
            return _Cancellation()

        @staticmethod
        def mark_cancellation_deactivated(request_id: int, deactivated_at: datetime) -> bool:
            marked_deactivated.append((request_id, deactivated_at))
            return True

    class _TenantRepo:
        @staticmethod
        def deactivate(tenant_id: int, *, updated_by: int | None = None) -> None:
            deactivated_tenants.append(tenant_id)

    svc._repo = _Repo()  # type: ignore[attr-defined]
    svc._tenant_repo = _TenantRepo()  # type: ignore[attr-defined]
    svc.clock = _Clock()  # type: ignore[attr-defined]
    monkeypatch.setattr(svc, "ensure_subscription", lambda _tenant: _Sub())
    monkeypatch.setattr(svc, "_load_resource_counts", lambda: {"knowledge_bases": 0})
    monkeypatch.setattr(svc, "_current_period", lambda: ("2026-05", None, datetime(2026, 5, 31, tzinfo=UTC), None))
    monkeypatch.setattr(svc, "_subscription_due_date", lambda _tenant_id, _subscription, _fallback: date(2026, 5, 31))

    result = BillingService.delete_service_access(  # type: ignore[misc]
        svc,
        _Tenant(),
        requested_by_user_id=11,
    )

    assert result.status == "deactivated"
    assert result.cancellation_request_id == 123
    assert deactivated_tenants == [7]
    assert marked_deactivated and marked_deactivated[0][0] == 123


def test_restore_subscription_renewal_clears_pending_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)

    class _Tenant:
        tenant_id = 7
        slug = "demo"

    class _Sub:
        pass

    class _Clock:
        @staticmethod
        def now() -> datetime:
            return datetime(2026, 5, 30, 8, 0, tzinfo=UTC)

    class _Cancellation:
        id = 123
        status = "deactivation_requested"
        deactivated_at = None

    restore_calls: list[int] = []

    class _Repo:
        @staticmethod
        def get_latest_cancellation_request(_tenant_id: int):
            return _Cancellation()

        @staticmethod
        def restore_latest_cancellation_request(tenant_id: int, restored_at: datetime) -> bool:
            restore_calls.append(tenant_id)
            return True

    svc._repo = _Repo()  # type: ignore[attr-defined]
    svc.clock = _Clock()  # type: ignore[attr-defined]
    monkeypatch.setattr(svc, "ensure_subscription", lambda _tenant: _Sub())
    monkeypatch.setattr(svc, "_current_period", lambda: ("2026-05", None, datetime(2026, 5, 31, tzinfo=UTC), None))
    monkeypatch.setattr(svc, "_subscription_due_date", lambda _tenant_id, _subscription, _fallback: date(2026, 5, 31))

    result = BillingService.restore_subscription_renewal(  # type: ignore[misc]
        svc,
        _Tenant(),
        requested_by_user_id=11,
    )

    assert result.status == "renewal_restored"
    assert result.cancellation_request_id == 123
    assert restore_calls == [7]


def test_process_cancellation_lifecycle_sends_notifications_and_handles_deactivation_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BillingService.__new__(BillingService)

    class _Clock:
        @staticmethod
        def now() -> datetime:
            return datetime(2026, 6, 10, 1, 0, tzinfo=UTC)

    class _Row:
        def __init__(
            self,
            *,
            req_id: int,
            tenant_id: int,
            tenant_slug: str,
            effective_at: datetime,
            deactivated_at: datetime | None = None,
            notice_two_days_sent_at: datetime | None = None,
            notice_one_day_sent_at: datetime | None = None,
            notice_expired_sent_at: datetime | None = None,
        ) -> None:
            self.id = req_id
            self.tenant_id = tenant_id
            self.tenant_slug = tenant_slug
            self.effective_at = effective_at
            self.deactivated_at = deactivated_at
            self.notice_two_days_sent_at = notice_two_days_sent_at
            self.notice_one_day_sent_at = notice_one_day_sent_at
            self.notice_expired_sent_at = notice_expired_sent_at

    rows = [
        _Row(req_id=1, tenant_id=101, tenant_slug="t101", effective_at=datetime(2026, 6, 12, 0, 0, tzinfo=UTC)),
        _Row(req_id=2, tenant_id=102, tenant_slug="t102", effective_at=datetime(2026, 6, 11, 0, 0, tzinfo=UTC)),
        _Row(req_id=3, tenant_id=103, tenant_slug="t103", effective_at=datetime(2026, 6, 3, 0, 0, tzinfo=UTC)),
        _Row(
            req_id=4,
            tenant_id=104,
            tenant_slug="t104",
            effective_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
            deactivated_at=datetime(2026, 6, 3, 0, 0, tzinfo=UTC),
            notice_expired_sent_at=datetime(2026, 6, 3, 1, 0, tzinfo=UTC),
        ),
    ]
    marked_two_days: list[int] = []
    marked_one_day: list[int] = []
    marked_expired: list[int] = []
    marked_deactivated: list[int] = []
    deleted_tenants: list[int] = []
    deactivated_tenants: list[int] = []
    dropped_schemas: list[str] = []
    invalidated_slugs: list[str] = []

    class _Repo:
        @staticmethod
        def list_cancellation_requests_for_lifecycle():
            return rows

        @staticmethod
        def mark_cancellation_notice_two_days_sent(request_id: int, sent_at: datetime) -> bool:
            marked_two_days.append(request_id)
            return True

        @staticmethod
        def mark_cancellation_notice_one_day_sent(request_id: int, sent_at: datetime) -> bool:
            marked_one_day.append(request_id)
            return True

        @staticmethod
        def mark_cancellation_notice_expired_sent(request_id: int, sent_at: datetime) -> bool:
            marked_expired.append(request_id)
            return True

        @staticmethod
        def mark_cancellation_deactivated(request_id: int, deactivated_at: datetime) -> bool:
            marked_deactivated.append(request_id)
            return True

        @staticmethod
        def hard_delete_tenant(tenant_id: int) -> bool:
            deleted_tenants.append(tenant_id)
            return True

    class _TenantRepo:
        @staticmethod
        def deactivate(tenant_id: int, *, updated_by: int | None = None) -> None:
            deactivated_tenants.append(tenant_id)

    class _Email:
        @staticmethod
        def send_email(to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
            return True

    class _SessionFactory:
        engine = object()

    svc._repo = _Repo()  # type: ignore[attr-defined]
    svc._tenant_repo = _TenantRepo()  # type: ignore[attr-defined]
    svc._email_service = _Email()  # type: ignore[attr-defined]
    svc._sf = _SessionFactory()  # type: ignore[attr-defined]
    svc.clock = _Clock()  # type: ignore[attr-defined]
    monkeypatch.setattr(svc, "_owner_email_for_tenant_slug", lambda _slug: "owner@example.com")
    monkeypatch.setattr("apps.billing.service.drop_tenant_schema", lambda _engine, slug: dropped_schemas.append(slug))
    monkeypatch.setattr("apps.billing.service.invalidate_tenant_cache", lambda slug: invalidated_slugs.append(slug))

    result = BillingService.process_cancellation_lifecycle(svc)  # type: ignore[misc]

    assert result["emails_sent"] == 3
    assert result["deactivated"] == 1
    assert result["deleted"] == 1
    assert marked_two_days == [1]
    assert marked_one_day == [2]
    assert marked_expired == [3]
    assert marked_deactivated == [3]
    assert deactivated_tenants == [103]
    assert deleted_tenants == [104]
    assert dropped_schemas == ["t104"]
    assert invalidated_slugs == ["t104"]
