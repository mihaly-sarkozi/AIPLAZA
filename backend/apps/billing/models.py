# backend/apps/billing/models.py
# Feladat: A billing app public schema SQLAlchemy ORM modelljeit definiálja. Catalog, subscription, question/training usage, invoice és debug state táblákat ír le tenantokra bontott előfizetés- és számlázási adatokhoz. Program-specifikus perzisztencia modell réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, Date as SQLADate, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import PublicBase
from shared.utils.clock import utc_now


DEFAULT_CURRENCY = "EUR"


def _utcnow() -> datetime:
    return utc_now()


class BillingCatalogEntryORM(PublicBase):
    __tablename__ = "billing_catalog_entries"
    __table_args__ = (
        UniqueConstraint("entry_type", "code", name="uq_billing_catalog_entry_type_code"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    entry_type = Column(String(32), nullable=False)
    code = Column(String(64), nullable=False)
    name = Column(String(120), nullable=False)
    currency = Column(String(8), nullable=False, default=DEFAULT_CURRENCY)
    price_cents = Column(Integer, nullable=False, default=0)
    included = Column(JSONB, nullable=False, default=dict)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())


class BillingSubscriptionORM(PublicBase):
    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_billing_subscriptions_tenant"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False)
    plan_code = Column(String(64), nullable=False, default="free")
    billing_period = Column(String(16), nullable=False, default="monthly")
    status = Column(String(24), nullable=False, default="trial")
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    extra_kb_count = Column(Integer, nullable=False, default=0)
    extra_storage_gb = Column(Integer, nullable=False, default=0)
    carryover_addon_questions = Column(Integer, nullable=False, default=0)
    carryover_training_chars = Column(BigInteger, nullable=False, default=0)
    scheduled_plan_code = Column(String(64), nullable=True)
    scheduled_billing_period = Column(String(16), nullable=True)
    scheduled_change_effective_period = Column(String(16), nullable=True)
    question_warning_period_key = Column(String(16), nullable=True)
    question_warning_level = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())


class BillingQuestionUsageORM(PublicBase):
    __tablename__ = "billing_question_usage"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "period_key", name="uq_billing_question_usage_tenant_user_period"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    period_key = Column(String(16), nullable=False, index=True)
    question_count = Column(Integer, nullable=False, default=0)
    last_question_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())


class BillingTrainingUsageORM(PublicBase):
    __tablename__ = "billing_training_usage"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period_key", name="uq_billing_training_usage_tenant_period"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    period_key = Column(String(16), nullable=False, index=True)
    trained_chars = Column(BigInteger, nullable=False, default=0)
    storage_bytes = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())


class BillingInvoiceORM(PublicBase):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_type", "period_key", name="uq_billing_invoice_tenant_type_period"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_type = Column(String(32), nullable=False)
    period_key = Column(String(16), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="issued")
    currency = Column(String(8), nullable=False, default=DEFAULT_CURRENCY)
    total_cents = Column(Integer, nullable=False, default=0)
    payment_method = Column(String(32), nullable=False, default="simulated_card")
    description = Column(String(255), nullable=False, default="")
    lines = Column(JSONB, nullable=False, default=list)
    issued_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    due_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())


class BillingPaymentEventORM(PublicBase):
    __tablename__ = "billing_payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_billing_payment_event_provider_event"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True)
    event_id = Column(String(128), nullable=False)
    event_type = Column(String(96), nullable=False)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(24), nullable=False, default="processed", index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True)


class TenantCancellationRequestORM(PublicBase):
    __tablename__ = "tenant_cancellation_requests"
    __table_args__ = ({"schema": "public"},)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_slug = Column(String(64), nullable=False, index=True)
    requested_by_user_id = Column(Integer, nullable=True, index=True)
    reason_code = Column(String(64), nullable=False)
    reason_text = Column(String(2000), nullable=False, default="")
    active_kb_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="deactivation_requested", index=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True)
    effective_at = Column(DateTime(timezone=True), nullable=True)
    notice_two_days_sent_at = Column(DateTime(timezone=True), nullable=True)
    notice_one_day_sent_at = Column(DateTime(timezone=True), nullable=True)
    notice_expired_sent_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    cleanup_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())


class BillingDebugStateORM(PublicBase):
    __tablename__ = "billing_debug_state"
    __table_args__ = ({"schema": "public"},)

    id = Column(Integer, primary_key=True)
    simulated_date = Column(SQLADate, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())
