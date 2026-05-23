# backend/apps/billing/calculations.py
# Feladat: A billing app tiszta dátum-, pénz- és időszak-kalkulációit tartalmazza. Havi/negydéves/éves ciklusok, kedvezmények, üzleti napok, storage kerekítés és pénzformázás helper funkcióit választja le a nagy BillingService-ről. Program-specifikus, állapotmentes billing calculation utility.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import calendar
import math
from datetime import UTC, date, datetime, timedelta

from shared.utils.clock import utc_now


def utcnow() -> datetime:
    return utc_now()


def money(cents: int) -> float:
    return round(int(cents) / 100.0, 2)


def round_storage_gb(storage_bytes: int | None) -> int:
    if not storage_bytes or storage_bytes <= 0:
        return 0
    gb = storage_bytes / (1024 ** 3)
    return max(1, int(math.ceil(gb)))


def is_business_day(day: date) -> bool:
    return day.weekday() < 5


def fifth_business_day(year: int, month: int) -> date:
    current = date(year, month, 5)
    while not is_business_day(current):
        current += timedelta(days=1)
    return current


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def add_months(year: int, month: int, count: int) -> tuple[int, int]:
    index = (year * 12 + (month - 1)) + count
    return index // 12, index % 12 + 1


def add_months_to_date(value: date, count: int) -> date:
    year, month = add_months(value.year, value.month, count)
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def current_month_period(now: datetime | None = None) -> tuple[str, datetime, datetime, date]:
    current = now or utcnow()
    due_this_month = fifth_business_day(current.year, current.month)
    if current.date() >= due_this_month:
        start_year, start_month = current.year, current.month
    else:
        start_year, start_month = previous_month(current.year, current.month)
    end_year, end_month = next_month(start_year, start_month)
    period_key = f"{start_year:04d}-{start_month:02d}"
    start_day = fifth_business_day(start_year, start_month)
    end_day = fifth_business_day(end_year, end_month)
    return (
        period_key,
        datetime.combine(start_day, datetime.min.time(), tzinfo=UTC),
        datetime.combine(end_day, datetime.min.time(), tzinfo=UTC),
        due_this_month,
    )


def discount_percent(billing_period: str) -> int:
    normalized = (billing_period or "monthly").strip().lower()
    if normalized == "quarterly":
        return 7
    if normalized == "yearly":
        return 15
    return 0


def apply_discount(price_cents: int, billing_period: str) -> int:
    discount = discount_percent(billing_period)
    if discount <= 0:
        return int(price_cents)
    return int(round(int(price_cents) * (100 - discount) / 100.0))


def plan_monthly_charge_cents_after_discount(price_cents: int, billing_period: str) -> int:
    discounted = apply_discount(int(price_cents), billing_period)
    return (int(discounted) // 100) * 100


def billing_period_multiplier(billing_period: str) -> int:
    normalized = (billing_period or "monthly").strip().lower()
    if normalized == "quarterly":
        return 3
    if normalized == "yearly":
        return 12
    return 1


def billing_period_label_hu(billing_period: str) -> str:
    normalized = (billing_period or "monthly").strip().lower()
    if normalized == "quarterly":
        return "negyedéves"
    if normalized == "yearly":
        return "éves"
    return "havi"


def charge_date_before_expiry(expiry_date: date) -> date:
    return expiry_date - timedelta(days=5)


__all__ = [
    "add_months",
    "add_months_to_date",
    "apply_discount",
    "billing_period_label_hu",
    "billing_period_multiplier",
    "charge_date_before_expiry",
    "current_month_period",
    "discount_percent",
    "fifth_business_day",
    "is_business_day",
    "money",
    "next_month",
    "plan_monthly_charge_cents_after_discount",
    "previous_month",
    "round_storage_gb",
    "utcnow",
]
