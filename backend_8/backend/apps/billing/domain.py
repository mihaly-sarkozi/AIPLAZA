# backend/apps/billing/domain.py
# Feladat: Billing service-ben használt egyszerű domain adatstruktúrákat tartalmaz. A catalogból képzett plan és addon DTO-kat választja le az application service-ről, hogy a service orchestration és domain shape külön maradjon. Program-specifikus billing domain helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BillingPlan:
    code: str
    name: str
    price_cents: int
    included_kbs: int
    included_storage_gb: int
    included_questions_monthly: int
    max_users: int | None
    trial_days: int
    included_training_chars: int


@dataclass(frozen=True)
class BillingAddon:
    code: str
    name: str
    price_cents: int
    metadata: dict[str, Any]


__all__ = ["BillingAddon", "BillingPlan"]
