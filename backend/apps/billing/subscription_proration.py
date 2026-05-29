# backend/apps/billing/subscription_proration.py
# Feladat: Előfizetés csomagváltási és proration kalkulációkat tartalmaz. Downgrade/scheduled change döntést, időarányos jóváírás számítást és upgrade utáni paid-until dátumot választ le a BillingService-ről. Program-specifikus subscription billing helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import date
from typing import Any

from apps.billing.calculations import (
    add_months,
    add_months_to_date,
    billing_period_multiplier,
    fifth_business_day,
    plan_monthly_charge_cents_after_discount,
)
from apps.billing.domain import BillingPlan
from apps.billing.models import DEFAULT_CURRENCY, BillingSubscriptionORM

TRAINING_INITIAL_FEE_CENTS_BY_PLAN: dict[str, int] = {
    "free": 0,
    "starter": 2900,
    "growth": 8900,
    "business": 48900,
}


def is_downgrade(
    *,
    current: BillingSubscriptionORM,
    next_plan_code: str,
    plans: dict[str, BillingPlan],
) -> bool:
    current_plan = plans.get(current.plan_code) or plans["free"]
    next_plan = plans.get(next_plan_code) or plans["free"]
    return (
        next_plan.price_cents < current_plan.price_cents
        or next_plan.included_kbs < current_plan.included_kbs
        or next_plan.included_storage_gb < current_plan.included_storage_gb
    )


def is_billing_period_downgrade(current_period: str, next_period: str) -> bool:
    rank = {"monthly": 1, "quarterly": 2, "yearly": 3}
    return rank.get((next_period or "monthly").strip().lower(), 1) < rank.get(
        (current_period or "monthly").strip().lower(),
        1,
    )


def is_scheduled_change(
    *,
    current: BillingSubscriptionORM,
    next_plan_code: str,
    next_period: str,
    plans: dict[str, BillingPlan],
) -> bool:
    return is_downgrade(current=current, next_plan_code=next_plan_code, plans=plans) or (
        current.plan_code == next_plan_code
        and is_billing_period_downgrade(current.billing_period, next_period)
    )


def proration_calendar_fraction(period_start: date, period_end_inclusive: date, today: date) -> tuple[int, int, float]:
    total_days = (period_end_inclusive - period_start).days + 1
    total_days = max(1, total_days)
    if today < period_start:
        remaining = total_days
    elif today > period_end_inclusive:
        remaining = 0
    else:
        remaining = (period_end_inclusive - today).days + 1
    remaining = max(0, min(remaining, total_days))
    fraction = remaining / total_days
    return total_days, remaining, fraction


def coverage_end_for_subscription(subscription: BillingSubscriptionORM, fallback_period_end: date) -> date:
    if subscription.trial_ends_at is not None and subscription.trial_ends_at.date() > fallback_period_end:
        return subscription.trial_ends_at.date()
    return fallback_period_end


def coverage_start_for_end(period_end: date, normalized_period: str) -> date:
    months = billing_period_multiplier(normalized_period)
    year, month = add_months(period_end.year, period_end.month, -months)
    return fifth_business_day(year, month)


def paid_until_after_upgrade(upgrade_date: date, normalized_period: str) -> date:
    months = billing_period_multiplier(normalized_period)
    return add_months_to_date(upgrade_date, months)


def training_initial_fee_cents_for_plan(plan_code: str) -> int:
    normalized = str(plan_code or "").strip().lower()
    return int(TRAINING_INITIAL_FEE_CENTS_BY_PLAN.get(normalized, 0))


def upgrade_training_initial_fee_cents(
    *,
    current_plan_code: str,
    next_plan_code: str,
) -> int:
    already_paid = training_initial_fee_cents_for_plan(current_plan_code)
    target_fee = training_initial_fee_cents_for_plan(next_plan_code)
    return max(0, target_fee - already_paid)


def compute_upgrade_proration(
    *,
    subscription: BillingSubscriptionORM,
    normalized_plan: str,
    normalized_period: str,
    plans: dict[str, BillingPlan],
    period_end: date,
    today: date,
) -> dict[str, Any] | None:
    if normalized_plan not in plans:
        return None
    if is_downgrade(current=subscription, next_plan_code=normalized_plan, plans=plans):
        return None
    if subscription.plan_code == normalized_plan and subscription.billing_period == normalized_period:
        return None
    current_plan = plans.get(subscription.plan_code) or plans["free"]
    next_plan = plans[normalized_plan]
    old_m = plan_monthly_charge_cents_after_discount(int(current_plan.price_cents), subscription.billing_period)
    new_m = plan_monthly_charge_cents_after_discount(int(next_plan.price_cents), normalized_period)
    delta_m = max(0, new_m - old_m)
    coverage_end = coverage_end_for_subscription(subscription, period_end)
    coverage_start = coverage_start_for_end(coverage_end, subscription.billing_period)
    total_d, rem_d, frac = proration_calendar_fraction(coverage_start, coverage_end, today)
    old_period_charge = old_m * billing_period_multiplier(subscription.billing_period)
    old_remaining_credit = int(round(old_period_charge * rem_d / max(1, total_d)))
    old_remaining_credit = max(0, old_remaining_credit)
    next_period_charge = new_m * billing_period_multiplier(normalized_period)
    paid_until = paid_until_after_upgrade(today, normalized_period)
    training_initial_fee_cents = upgrade_training_initial_fee_cents(
        current_plan_code=subscription.plan_code,
        next_plan_code=normalized_plan,
    )
    total_charge = max(0, next_period_charge - old_remaining_credit) + max(0, int(training_initial_fee_cents))
    return {
        "immediate_use": True,
        "total_period_days": total_d,
        "remaining_period_days": rem_d,
        "proration_fraction": round(frac, 4),
        "old_plan_code": subscription.plan_code,
        "new_plan_code": normalized_plan,
        "old_monthly_cents": old_m,
        "new_monthly_cents": new_m,
        "delta_monthly_cents": delta_m,
        "prorated_charge_cents": 0,
        "old_remaining_credit_cents": old_remaining_credit,
        "next_period_charge_cents": next_period_charge,
        "training_initial_fee_cents": int(training_initial_fee_cents),
        "total_charge_cents": total_charge,
        "paid_until_iso": paid_until.isoformat(),
        "currency": DEFAULT_CURRENCY,
    }


__all__ = [
    "compute_upgrade_proration",
    "coverage_end_for_subscription",
    "coverage_start_for_end",
    "is_billing_period_downgrade",
    "is_downgrade",
    "is_scheduled_change",
    "training_initial_fee_cents_for_plan",
    "upgrade_training_initial_fee_cents",
    "paid_until_after_upgrade",
    "proration_calendar_fraction",
]
