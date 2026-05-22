# backend/apps/billing/runtime.py
# Feladat: A billing app runtime exportjait gyűjti össze. ORM modelleket, repositoryt, service-t, worker-t, payment result típust, routert és schema hook regisztrációt ad stabil importfelületként. Program-specifikus runtime compatibility belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from apps.billing.catalog import default_catalog_rows
from apps.billing.calculations import (
    billing_period_multiplier,
    charge_date_before_expiry,
    current_month_period,
    money,
    round_storage_gb,
)
from apps.billing.debug_clock import BillingDebugClock
from apps.billing.domain import BillingAddon, BillingPlan
from apps.billing.models import (
    BillingCatalogEntryORM,
    BillingInvoiceORM,
    BillingPaymentEventORM,
    BillingQuestionUsageORM,
    BillingSubscriptionORM,
    BillingTrainingUsageORM,
)
from apps.billing.payment import PaymentExecutionResult
from apps.billing.repositories import BillingRepository
from apps.billing.router import get_billing_service, router
from apps.billing.schema_hooks import register_billing_tenant_hooks
from apps.billing.service import BillingService
from apps.billing.worker import BillingWorker

__all__ = [
    "BillingCatalogEntryORM",
    "BillingAddon",
    "BillingDebugClock",
    "BillingInvoiceORM",
    "BillingPaymentEventORM",
    "BillingPlan",
    "BillingQuestionUsageORM",
    "BillingRepository",
    "BillingService",
    "BillingSubscriptionORM",
    "BillingTrainingUsageORM",
    "BillingWorker",
    "PaymentExecutionResult",
    "billing_period_multiplier",
    "charge_date_before_expiry",
    "current_month_period",
    "default_catalog_rows",
    "get_billing_service",
    "money",
    "register_billing_tenant_hooks",
    "round_storage_gb",
    "router",
]
