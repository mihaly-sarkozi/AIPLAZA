from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_BILLING_CURRENCY = "EUR"


class BillingCatalogEntryResponse(BaseModel):
    entry_type: str
    code: str
    name: str
    currency: str
    price_cents: int
    price: float
    included: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BillingSubscriptionUpdateRequest(BaseModel):
    plan_code: str
    billing_period: str = "monthly"


class BillingAddonPurchaseRequest(BaseModel):
    addon_code: str
    quantity: int = 1


class BillingDebugDateRequest(BaseModel):
    simulated_date: str | None = None


class BillingDebugDateResponse(BaseModel):
    enabled: bool
    simulated_date: str | None = None
    current_date: str


class BillingDebugBillingRunRequest(BaseModel):
    outcome: str


class BillingDebugBillingRunResponse(BaseModel):
    status: str
    message: str
    billing_date: str
    next_billing_date: str | None = None
    grace_until: str | None = None


class BillingUserQuestionUsageResponse(BaseModel):
    user_id: int
    name: str | None = None
    email: str = ""
    question_count: int


class BillingInvoiceResponse(BaseModel):
    id: int
    invoice_type: str
    period_key: str
    status: str
    currency: str
    total_cents: int
    total: float
    description: str
    issued_at: datetime
    due_at: datetime
    lines: list[dict[str, Any]]


class BillingOverviewResponse(BaseModel):
    current_period_key: str
    current_period_start_iso: str
    current_period_end_iso: str
    catalog: list[BillingCatalogEntryResponse]
    subscription: dict[str, Any]
    limits: dict[str, Any]
    usage: dict[str, Any]
    invoices: list[BillingInvoiceResponse]
    estimated_next_invoice: dict[str, Any]
    payment_warning: dict[str, Any] | None = None
    demo_mode: bool = False


class TenantStatisticsResponse(BaseModel):
    period: dict[str, Any]
    summary: dict[str, Any]
    queries: dict[str, Any]
    usage: dict[str, Any]
    training: dict[str, Any]
    domains: dict[str, Any]
    package: dict[str, Any]


class BillingAccessStatusResponse(BaseModel):
    restricted: bool
    payment_warning: dict[str, Any] | None = None


class BillingUpgradePreviewResponse(BaseModel):
    immediate_use: bool = True
    total_period_days: int
    remaining_period_days: int
    proration_fraction: float
    old_plan_code: str
    new_plan_code: str
    old_monthly_cents: int
    new_monthly_cents: int
    delta_monthly_cents: int
    prorated_charge_cents: int
    old_remaining_credit_cents: int
    next_period_charge_cents: int
    total_charge_cents: int
    paid_until_iso: str
    currency: str = DEFAULT_BILLING_CURRENCY


class BillingUpgradeCompleteResponse(BaseModel):
    status: str
    prorated_charge_cents: int
    prorated_charge: float
    old_remaining_credit_cents: int
    next_period_charge_cents: int
    total_charge_cents: int
    paid_until_iso: str

