# backend/apps/billing/schemas.py
# Feladat: A billing app HTTP request és response Pydantic szerződéseit tartalmazza. Előfizetés, addon vásárlás, debug futtatás, számla, overview, access status és upgrade preview/complete payloadokat definiál validált bemenetekkel. Program-specifikus web schema réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

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
    plan_code: str = Field(..., min_length=1, max_length=64)
    billing_period: str = "monthly"

    @field_validator("billing_period")
    @classmethod
    def validate_billing_period(cls, value: str) -> str:
        normalized = (value or "monthly").strip().lower()
        if normalized not in {"monthly", "quarterly", "yearly"}:
            raise ValueError("Invalid billing period.")
        return normalized

    @field_validator("plan_code")
    @classmethod
    def normalize_plan_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or not normalized[0].isalnum() or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in normalized):
            raise ValueError("Invalid plan code.")
        return normalized


class BillingCancellationRequest(BaseModel):
    reason_code: str = Field(..., min_length=1, max_length=64)
    reason_text: str = Field(default="", max_length=2000)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"too_expensive", "not_using", "not_satisfied", "missing_features", "other"}:
            raise ValueError("Invalid cancellation reason.")
        return normalized

    @field_validator("reason_text")
    @classmethod
    def normalize_reason_text(cls, value: str) -> str:
        return (value or "").strip()


class BillingCancellationResponse(BaseModel):
    status: str
    message: str
    active_kb_count: int = 0
    cancellation_request_id: int | None = None
    current_period_end_iso: str | None = None


class BillingAddonPurchaseRequest(BaseModel):
    addon_code: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=100)

    @field_validator("addon_code")
    @classmethod
    def normalize_addon_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or not normalized[0].isalnum() or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in normalized):
            raise ValueError("Invalid addon code.")
        return normalized


class BillingDebugDateRequest(BaseModel):
    simulated_date: str | None = None


class BillingDebugDateResponse(BaseModel):
    enabled: bool
    simulated_date: str | None = None
    current_date: str


class BillingDebugBillingRunRequest(BaseModel):
    outcome: str

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"success", "failed"}:
            raise ValueError("Invalid billing debug outcome.")
        return normalized


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
    training_initial_fee_cents: int = 0
    total_charge_cents: int
    paid_until_iso: str
    currency: str = DEFAULT_BILLING_CURRENCY


class BillingUpgradeCompleteResponse(BaseModel):
    status: str
    prorated_charge_cents: int
    prorated_charge: float
    old_remaining_credit_cents: int
    next_period_charge_cents: int
    training_initial_fee_cents: int = 0
    total_charge_cents: int
    paid_until_iso: str

