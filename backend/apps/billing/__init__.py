# backend/apps/billing/__init__.py
# Feladat: A billing app publikus exportfelülete. A module assemblyt, repositoryt, routert, service-t és background workert adja tovább az alkalmazás manifestje és más modulok felé. Program-specifikus számlázási app belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from apps.billing.catalog import default_catalog_rows
from apps.billing.calculations import billing_period_multiplier, charge_date_before_expiry, money
from apps.billing.debug_clock import BillingDebugClock
from apps.billing.domain import BillingAddon, BillingPlan
from apps.billing.bootstrap.app_module import BillingAppModule, get_module
from apps.billing.repositories import BillingRepository
from apps.billing.router import router
from apps.billing.service import BillingService
from apps.billing.worker import BillingWorker

__all__ = [
    "BillingAddon",
    "BillingAppModule",
    "BillingDebugClock",
    "BillingPlan",
    "BillingRepository",
    "BillingService",
    "BillingWorker",
    "billing_period_multiplier",
    "charge_date_before_expiry",
    "default_catalog_rows",
    "get_module",
    "money",
    "router",
]
