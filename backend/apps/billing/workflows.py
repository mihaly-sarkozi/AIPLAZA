from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from core.kernel.clock import Clock


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class SubscriptionStateMachine:
    clock: Clock

    def resolve(self, subscription: Any, *, overdue_invoice: Any | None = None, now: datetime | None = None) -> str:
        current = now or self.clock.now()
        if overdue_invoice is not None and getattr(overdue_invoice, "status", None) == "issued":
            due_at = getattr(overdue_invoice, "due_at", None)
            if due_at is not None and due_at <= current:
                return SubscriptionStatus.RESTRICTED.value

        if getattr(subscription, "plan_code", None) == "free":
            trial_ends_at = getattr(subscription, "trial_ends_at", None)
            if trial_ends_at is not None and trial_ends_at <= current:
                return SubscriptionStatus.RESTRICTED.value
            return SubscriptionStatus.TRIAL.value

        return SubscriptionStatus.ACTIVE.value


@dataclass
class RenewalUseCase:
    service: Any
    state_machine: SubscriptionStateMachine
    clock: Clock

    def execute(self, tenant: Any, subscription: Any, *, period_key: str, due_this_month) -> Any:
        now = self.clock.now()
        if (
            now.date() >= due_this_month
            and getattr(subscription, "scheduled_change_effective_period", None) == period_key
            and getattr(subscription, "scheduled_plan_code", None)
        ):
            subscription = self.service._repo.upsert_subscription(
                tenant.tenant_id,
                plan_code=subscription.scheduled_plan_code,
                billing_period=subscription.scheduled_billing_period or subscription.billing_period,
                status=SubscriptionStatus.ACTIVE.value if subscription.scheduled_plan_code != "free" else SubscriptionStatus.TRIAL.value,
                trial_started_at=subscription.trial_started_at if subscription.scheduled_plan_code == "free" else None,
                trial_ends_at=subscription.trial_ends_at if subscription.scheduled_plan_code == "free" else None,
                extra_kb_count=int(subscription.extra_kb_count or 0),
                extra_storage_gb=int(subscription.extra_storage_gb or 0),
                carryover_addon_questions=int(subscription.carryover_addon_questions or 0),
                carryover_training_chars=int(subscription.carryover_training_chars or 0),
                scheduled_plan_code=None,
                scheduled_billing_period=None,
                scheduled_change_effective_period=None,
                question_warning_period_key=None,
                question_warning_level=0,
            )
        return subscription


@dataclass
class RestrictionUseCase:
    service: Any
    state_machine: SubscriptionStateMachine
    clock: Clock

    def sync_status(self, tenant: Any, subscription: Any) -> Any:
        overdue_invoice = self.service._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription")
        next_status = self.state_machine.resolve(subscription, overdue_invoice=overdue_invoice, now=self.clock.now())
        if next_status == subscription.status:
            return subscription
        return self.service._repo.upsert_subscription(
            tenant.tenant_id,
            plan_code=subscription.plan_code,
            billing_period=subscription.billing_period,
            status=next_status,
            trial_started_at=subscription.trial_started_at,
            trial_ends_at=subscription.trial_ends_at,
            extra_kb_count=int(subscription.extra_kb_count or 0),
            extra_storage_gb=int(subscription.extra_storage_gb or 0),
            carryover_addon_questions=int(subscription.carryover_addon_questions or 0),
            carryover_training_chars=int(subscription.carryover_training_chars or 0),
            scheduled_plan_code=subscription.scheduled_plan_code,
            scheduled_billing_period=subscription.scheduled_billing_period,
            scheduled_change_effective_period=subscription.scheduled_change_effective_period,
            question_warning_period_key=subscription.question_warning_period_key,
            question_warning_level=int(subscription.question_warning_level or 0),
        )

    def assert_not_restricted(self, tenant: Any, subscription: Any) -> tuple[bool, str | None]:
        current = self.sync_status(tenant, subscription)
        if current.status != SubscriptionStatus.RESTRICTED.value:
            return True, None
        return False, "Az előfizetés korlátozott állapotban van. Rendezd a számlázást vagy válassz új csomagot."


@dataclass
class InvoicingUseCase:
    service: Any
    clock: Clock

    def execute(
        self,
        tenant: Any,
        subscription: Any,
        *,
        next_period_key: str,
        next_charge_date,
        plan_map: dict[str, Any],
    ) -> None:
        now = self.clock.now()
        if subscription.plan_code == "free":
            return
        if subscription.status == SubscriptionStatus.RESTRICTED.value:
            return
        if now.date() < next_charge_date:
            return
        invoice_exists = self.service._repo.get_invoice(tenant.tenant_id, "monthly_subscription", next_period_key)
        if invoice_exists is not None:
            return
        plan = plan_map.get(subscription.plan_code) or plan_map["free"]
        total_cents = self.service._estimate_next_invoice(subscription)["total_cents"]
        self.service._repo.create_invoice(
            tenant.tenant_id,
            invoice_type="monthly_subscription",
            period_key=next_period_key,
            currency=self.service.default_currency,
            total_cents=total_cents,
            description=f"{plan.name} {self.service._billing_period_label(subscription.billing_period)} díj",
            lines=[
                {
                    "code": plan.code,
                    "name": plan.name,
                    "billing_period": subscription.billing_period,
                    "period_multiplier": self.service._billing_period_multiplier(subscription.billing_period),
                    "unit_price_cents": self.service._plan_monthly_charge_after_discount(
                        plan.price_cents, subscription.billing_period
                    ),
                    "extra_kb_count": int(subscription.extra_kb_count or 0),
                    "extra_storage_gb": int(subscription.extra_storage_gb or 0),
                    "total_cents": total_cents,
                }
            ],
            due_at=datetime.combine(next_charge_date, datetime.min.time(), tzinfo=now.tzinfo) + timedelta(0),
            status="issued",
        )


@dataclass
class BillingCycleProcessor:
    service: Any
    renewal_use_case: RenewalUseCase
    restriction_use_case: RestrictionUseCase
    invoicing_use_case: InvoicingUseCase
    clock: Clock

    def process(self) -> None:
        period_key, _, period_end_dt, due_this_month = self.service._current_period()
        plan_map = self.service._plan_map()
        next_period_key = f"{period_end_dt.year:04d}-{period_end_dt.month:02d}"
        next_charge_date = self.service._charge_date_before_expiry(period_end_dt.date())

        for tenant_row in self.service._repo.list_active_tenants():
            tenant = self.service._tenant_repo.get_snapshot_by_slug(tenant_row.slug)
            if tenant is None:
                continue
            subscription = self.service.ensure_subscription(tenant)
            subscription = self.renewal_use_case.execute(
                tenant,
                subscription,
                period_key=period_key,
                due_this_month=due_this_month,
            )
            subscription = self.restriction_use_case.sync_status(tenant, subscription)
            self.invoicing_use_case.execute(
                tenant,
                subscription,
                next_period_key=next_period_key,
                next_charge_date=next_charge_date,
                plan_map=plan_map,
            )
            self.service._sync_tenant_config(tenant, subscription)
