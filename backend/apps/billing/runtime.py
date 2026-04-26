from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import math
import threading
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError

from apps.billing.workflows import (
    BillingCycleProcessor,
    InvoicingUseCase,
    RenewalUseCase,
    RestrictionUseCase,
    SubscriptionStateMachine,
    SubscriptionStatus,
)
from core.capabilities.users.dto import User
from core.capabilities.users.models.user_orm import UserORM
from core.di import RequiredTenantContextDep, get_service, service_dependency
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from core.extensions.tenant.models.tenant_orm import TenantORM
from core.extensions.tenant.repositories import TenantRepository
from core.extensions.tenant.service import TenantSchemaHook, install_schema_tables, register_tenant_schema_hooks, run_schema_statements
from shared.utils.clock import Clock, SystemClock, utc_now
from core.kernel.db.model_bases import AuthBase, PublicBase
from core.platform.auth.auth_dependencies import require_role


DEFAULT_CURRENCY = "EUR"
DEFAULT_POLL_SECONDS = 3600
QUESTION_WARNING_LEVELS = (90, 100)


def _utcnow() -> datetime:
    return utc_now()


def _money(cents: int) -> float:
    return round(int(cents) / 100.0, 2)


def _round_storage_gb(storage_bytes: int | None) -> int:
    if not storage_bytes or storage_bytes <= 0:
        return 0
    gb = storage_bytes / (1024 ** 3)
    return max(1, int(math.ceil(gb)))


def _is_business_day(day: date) -> bool:
    return day.weekday() < 5


def _fifth_business_day(year: int, month: int) -> date:
    current = date(year, month, 5)
    while not _is_business_day(current):
        current += timedelta(days=1)
    return current


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _current_month_period(now: datetime | None = None) -> tuple[str, datetime, datetime, date]:
    current = now or _utcnow()
    due_this_month = _fifth_business_day(current.year, current.month)
    if current.date() >= due_this_month:
        start_year, start_month = current.year, current.month
    else:
        start_year, start_month = _previous_month(current.year, current.month)
    end_year, end_month = _next_month(start_year, start_month)
    period_key = f"{start_year:04d}-{start_month:02d}"
    start_day = _fifth_business_day(start_year, start_month)
    end_day = _fifth_business_day(end_year, end_month)
    return (
        period_key,
        datetime.combine(start_day, datetime.min.time(), tzinfo=UTC),
        datetime.combine(end_day, datetime.min.time(), tzinfo=UTC),
        due_this_month,
    )


def _discount_percent(billing_period: str) -> int:
    normalized = (billing_period or "monthly").strip().lower()
    if normalized == "quarterly":
        return 7
    if normalized == "yearly":
        return 15
    return 0


def _apply_discount(price_cents: int, billing_period: str) -> int:
    discount = _discount_percent(billing_period)
    if discount <= 0:
        return int(price_cents)
    return int(round(int(price_cents) * (100 - discount) / 100.0))


def _plan_monthly_charge_cents_after_discount(price_cents: int, billing_period: str) -> int:
    discounted = _apply_discount(int(price_cents), billing_period)
    return (int(discounted) // 100) * 100


def _billing_period_multiplier(billing_period: str) -> int:
    normalized = (billing_period or "monthly").strip().lower()
    if normalized == "quarterly":
        return 3
    if normalized == "yearly":
        return 12
    return 1


def _billing_period_label_hu(billing_period: str) -> str:
    normalized = (billing_period or "monthly").strip().lower()
    if normalized == "quarterly":
        return "negyedéves"
    if normalized == "yearly":
        return "éves"
    return "havi"


def _charge_date_before_expiry(expiry_date: date) -> date:
    return expiry_date - timedelta(days=5)


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


class BillingUserQuestionUsageResponse(BaseModel):
    user_id: int
    name: str | None = None
    email: str = ""
    question_count: int


class BillingInvoiceResponse(BaseModel):
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
    demo_mode: bool = False


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
    currency: str = DEFAULT_CURRENCY


class BillingUpgradeCompleteResponse(BaseModel):
    status: str
    prorated_charge_cents: int
    prorated_charge: float


class BillingRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]):
        self._sf = session_factory

    def ensure_storage(self) -> None:
        tables = (
            BillingCatalogEntryORM.__table__,
            BillingSubscriptionORM.__table__,
            BillingQuestionUsageORM.__table__,
            BillingTrainingUsageORM.__table__,
            BillingInvoiceORM.__table__,
        )
        engine = self._sf.engine
        PublicBase.metadata.create_all(bind=engine, tables=list(tables))
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_billing_question_usage_tenant_period
                    ON public.billing_question_usage (tenant_id, period_key)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_billing_invoices_tenant_issued
                    ON public.billing_invoices (tenant_id, issued_at DESC)
                    """
                )
            )
            commit = getattr(conn, "commit", None)
            if callable(commit):
                commit()

    def seed_catalog(self, rows: list[dict[str, Any]]) -> None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            for row in rows:
                existing = (
                    db.query(BillingCatalogEntryORM)
                    .filter(
                        BillingCatalogEntryORM.entry_type == row["entry_type"],
                        BillingCatalogEntryORM.code == row["code"],
                    )
                    .first()
                )
                if existing is None:
                    db.add(BillingCatalogEntryORM(**row))
                else:
                    existing.name = row["name"]
                    existing.currency = row["currency"]
                    existing.price_cents = row["price_cents"]
                    existing.included = row.get("included") or {}
                    existing.metadata_json = row.get("metadata_json") or {}
                    existing.is_active = bool(row.get("is_active", True))
                    existing.updated_at = _utcnow()
            db.commit()

    def list_catalog(self) -> list[BillingCatalogEntryORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingCatalogEntryORM)
                .filter(BillingCatalogEntryORM.is_active.is_(True))
                .order_by(BillingCatalogEntryORM.entry_type.asc(), BillingCatalogEntryORM.price_cents.asc())
                .all()
            )

    def get_subscription(self, tenant_id: int) -> BillingSubscriptionORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return db.query(BillingSubscriptionORM).filter(BillingSubscriptionORM.tenant_id == tenant_id).first()

    def upsert_subscription(
        self,
        tenant_id: int,
        *,
        plan_code: str,
        billing_period: str,
        status: str,
        trial_started_at: datetime | None,
        trial_ends_at: datetime | None,
        extra_kb_count: int = 0,
        extra_storage_gb: int = 0,
        carryover_addon_questions: int = 0,
        carryover_training_chars: int = 0,
        scheduled_plan_code: str | None = None,
        scheduled_billing_period: str | None = None,
        scheduled_change_effective_period: str | None = None,
        question_warning_period_key: str | None = None,
        question_warning_level: int = 0,
    ) -> BillingSubscriptionORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingSubscriptionORM).filter(BillingSubscriptionORM.tenant_id == tenant_id).first()
            if row is None:
                row = BillingSubscriptionORM(
                    tenant_id=tenant_id,
                    plan_code=plan_code,
                    billing_period=billing_period,
                    status=status,
                    trial_started_at=trial_started_at,
                    trial_ends_at=trial_ends_at,
                    extra_kb_count=extra_kb_count,
                    extra_storage_gb=extra_storage_gb,
                    carryover_addon_questions=carryover_addon_questions,
                    carryover_training_chars=carryover_training_chars,
                    scheduled_plan_code=scheduled_plan_code,
                    scheduled_billing_period=scheduled_billing_period,
                    scheduled_change_effective_period=scheduled_change_effective_period,
                    question_warning_period_key=question_warning_period_key,
                    question_warning_level=question_warning_level,
                )
                db.add(row)
            else:
                row.plan_code = plan_code
                row.billing_period = billing_period
                row.status = status
                row.trial_started_at = trial_started_at
                row.trial_ends_at = trial_ends_at
                row.extra_kb_count = extra_kb_count
                row.extra_storage_gb = extra_storage_gb
                row.carryover_addon_questions = carryover_addon_questions
                row.carryover_training_chars = carryover_training_chars
                row.scheduled_plan_code = scheduled_plan_code
                row.scheduled_billing_period = scheduled_billing_period
                row.scheduled_change_effective_period = scheduled_change_effective_period
                row.question_warning_period_key = question_warning_period_key
                row.question_warning_level = question_warning_level
                row.updated_at = _utcnow()
            db.commit()
            db.refresh(row)
            return row

    def upsert_question_usage(self, tenant_id: int, user_id: int, period_key: str, increment: int = 1) -> BillingQuestionUsageORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(BillingQuestionUsageORM)
                .filter(
                    BillingQuestionUsageORM.tenant_id == tenant_id,
                    BillingQuestionUsageORM.user_id == user_id,
                    BillingQuestionUsageORM.period_key == period_key,
                )
                .first()
            )
            if row is None:
                row = BillingQuestionUsageORM(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    period_key=period_key,
                    question_count=max(0, int(increment)),
                    last_question_at=_utcnow(),
                )
                db.add(row)
            else:
                row.question_count = int(row.question_count or 0) + max(0, int(increment))
                row.last_question_at = _utcnow()
                row.updated_at = _utcnow()
            db.commit()
            db.refresh(row)
            return row

    def list_question_usage(self, tenant_id: int, period_key: str) -> list[BillingQuestionUsageORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingQuestionUsageORM)
                .filter(
                    BillingQuestionUsageORM.tenant_id == tenant_id,
                    BillingQuestionUsageORM.period_key == period_key,
                )
                .order_by(BillingQuestionUsageORM.question_count.desc(), BillingQuestionUsageORM.user_id.asc())
                .all()
            )

    def get_training_usage(self, tenant_id: int, period_key: str) -> BillingTrainingUsageORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingTrainingUsageORM)
                .filter(
                    BillingTrainingUsageORM.tenant_id == tenant_id,
                    BillingTrainingUsageORM.period_key == period_key,
                )
                .first()
            )

    def increment_training_usage(
        self,
        tenant_id: int,
        period_key: str,
        *,
        trained_chars: int = 0,
        storage_bytes: int = 0,
    ) -> BillingTrainingUsageORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(BillingTrainingUsageORM)
                .filter(
                    BillingTrainingUsageORM.tenant_id == tenant_id,
                    BillingTrainingUsageORM.period_key == period_key,
                )
                .first()
            )
            d_chars = max(0, int(trained_chars))
            d_bytes = max(0, int(storage_bytes))
            if row is None:
                row = BillingTrainingUsageORM(
                    tenant_id=tenant_id,
                    period_key=period_key,
                    trained_chars=d_chars,
                    storage_bytes=d_bytes,
                )
                db.add(row)
            else:
                row.trained_chars = int(row.trained_chars or 0) + d_chars
                row.storage_bytes = int(row.storage_bytes or 0) + d_bytes
            db.commit()
            db.refresh(row)
            return row

    def create_invoice(
        self,
        tenant_id: int,
        *,
        invoice_type: str,
        period_key: str,
        currency: str,
        total_cents: int,
        description: str,
        lines: list[dict[str, Any]],
        due_at: datetime,
        status: str = "simulated_paid",
    ) -> BillingInvoiceORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = BillingInvoiceORM(
                tenant_id=tenant_id,
                invoice_type=invoice_type,
                period_key=period_key,
                currency=currency,
                total_cents=total_cents,
                description=description,
                lines=lines,
                due_at=due_at,
                status=status,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def get_invoice(self, tenant_id: int, invoice_type: str, period_key: str) -> BillingInvoiceORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type == invoice_type,
                    BillingInvoiceORM.period_key == period_key,
                )
                .first()
            )

    def list_recent_invoices(self, tenant_id: int, limit: int = 12) -> list[BillingInvoiceORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(BillingInvoiceORM.tenant_id == tenant_id)
                .order_by(BillingInvoiceORM.issued_at.desc())
                .limit(limit)
                .all()
            )

    def get_latest_invoice_for_type(self, tenant_id: int, invoice_type: str) -> BillingInvoiceORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type == invoice_type,
                )
                .order_by(BillingInvoiceORM.issued_at.desc())
                .first()
            )

    def list_active_tenants(self) -> list[TenantORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return db.query(TenantORM).filter(TenantORM.is_active.is_(True)).all()


class BillingService:
    def __init__(
        self,
        repo: BillingRepository,
        tenant_repo: TenantRepository,
        session_factory: Callable[[], AbstractContextManager[Any]],
        user_repository,
        email_service,
        clock: Clock | None = None,
    ) -> None:
        self._repo = repo
        self._tenant_repo = tenant_repo
        self._sf = session_factory
        self._user_repository = user_repository
        self._email_service = email_service
        self.clock = clock or SystemClock()
        self.default_currency = DEFAULT_CURRENCY
        self._state_machine = SubscriptionStateMachine(self.clock)
        self._renewal_use_case = RenewalUseCase(self, self._state_machine, self.clock)
        self._restriction_use_case = RestrictionUseCase(self, self._state_machine, self.clock)
        self._invoicing_use_case = InvoicingUseCase(self, self.clock)
        self._cycle_processor = BillingCycleProcessor(
            self,
            self._renewal_use_case,
            self._restriction_use_case,
            self._invoicing_use_case,
            self.clock,
        )

    def ensure_storage(self) -> None:
        self._repo.ensure_storage()
        self._repo.seed_catalog(self._default_catalog_rows())

    @staticmethod
    def _billing_period_label(billing_period: str) -> str:
        return _billing_period_label_hu(billing_period)

    @staticmethod
    def _billing_period_multiplier(billing_period: str) -> int:
        return _billing_period_multiplier(billing_period)

    @staticmethod
    def _plan_monthly_charge_after_discount(price_cents: int, billing_period: str) -> int:
        return _plan_monthly_charge_cents_after_discount(price_cents, billing_period)

    @staticmethod
    def _charge_date_before_expiry(expiry_date: date) -> date:
        return _charge_date_before_expiry(expiry_date)

    def _default_catalog_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "entry_type": "plan",
                "code": "free",
                "name": "Ingyenes próba",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 0,
                "included": {
                    "knowledge_bases": 1,
                    "storage_gb": 1,
                    "questions_monthly": 100,
                    "training_chars": 100000,
                    "max_users": 5,
                    "trial_days": 7,
                },
                "metadata_json": {
                    "description": "Belépő csomag kipróbálásra",
                    "training_note": "(kb. 50 oldalas könyv)",
                },
                "is_active": True,
            },
            {
                "entry_type": "plan",
                "code": "starter",
                "name": "Starter",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 2900,
                "included": {
                    "knowledge_bases": 1,
                    "storage_gb": 1,
                    "questions_monthly": 500,
                    "training_chars": 500000,
                    "max_users": None,
                    "trial_days": 0,
                },
                "metadata_json": {"description": "1–2 fős csapatoknak"},
                "is_active": True,
            },
            {
                "entry_type": "plan",
                "code": "growth",
                "name": "Growth",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 5900,
                "included": {
                    "knowledge_bases": 3,
                    "storage_gb": 5,
                    "questions_monthly": 2000,
                    "training_chars": 500000,
                    "max_users": None,
                    "trial_days": 0,
                },
                "metadata_json": {"description": "Komolyabb felhasználás"},
                "is_active": True,
            },
            {
                "entry_type": "plan",
                "code": "business",
                "name": "Business",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 12900,
                "included": {
                    "knowledge_bases": 10,
                    "storage_gb": 10,
                    "questions_monthly": 5000,
                    "training_chars": 1000000,
                    "max_users": None,
                    "trial_days": 0,
                },
                "metadata_json": {"description": "Professzionális cégeknek"},
                "is_active": True,
            },
            {
                "entry_type": "addon",
                "code": "question_pack_100",
                "name": "100 extra kérdés",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 120,
                "included": {"questions": 100},
                "metadata_json": {"carryover": True, "kind": "questions"},
                "is_active": True,
            },
            {
                "entry_type": "addon",
                "code": "question_pack_500",
                "name": "500 extra kérdés",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 500,
                "included": {"questions": 500},
                "metadata_json": {"carryover": True, "kind": "questions"},
                "is_active": True,
            },
            {
                "entry_type": "addon",
                "code": "extra_kb",
                "name": "Extra tudástár / hó",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 500,
                "included": {"knowledge_bases": 1},
                "metadata_json": {"recurring": True, "kind": "knowledge_bases"},
                "is_active": True,
            },
            {
                "entry_type": "addon",
                "code": "extra_storage_gb",
                "name": "Extra tárhely GB / hó",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 500,
                "included": {"storage_gb": 1},
                "metadata_json": {"recurring": True, "kind": "storage_gb"},
                "is_active": True,
            },
            {
                "entry_type": "addon",
                "code": "training_initial_500k",
                "name": "Első betanítás 500k karakterig",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 4900,
                "included": {"training_chars": 500000},
                "metadata_json": {"recurring": False, "kind": "training_chars"},
                "is_active": True,
            },
            {
                "entry_type": "addon",
                "code": "training_extra_500k",
                "name": "További betanítás 500k karakter",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 2900,
                "included": {"training_chars": 500000},
                "metadata_json": {"recurring": False, "kind": "training_chars"},
                "is_active": True,
            },
            {
                "entry_type": "discount",
                "code": "quarterly_7",
                "name": "Negyedéves kedvezmény",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 0,
                "included": {},
                "metadata_json": {"billing_period": "quarterly", "discount_percent": 7},
                "is_active": True,
            },
            {
                "entry_type": "discount",
                "code": "yearly_15",
                "name": "Éves kedvezmény",
                "currency": DEFAULT_CURRENCY,
                "price_cents": 0,
                "included": {},
                "metadata_json": {"billing_period": "yearly", "discount_percent": 15},
                "is_active": True,
            },
        ]

    def _plan_map(self) -> dict[str, BillingPlan]:
        result: dict[str, BillingPlan] = {}
        for row in self._repo.list_catalog():
            if row.entry_type != "plan":
                continue
            included = dict(row.included or {})
            result[row.code] = BillingPlan(
                code=row.code,
                name=row.name,
                price_cents=int(row.price_cents or 0),
                included_kbs=int(included.get("knowledge_bases") or 0),
                included_storage_gb=int(included.get("storage_gb") or 0),
                included_questions_monthly=int(included.get("questions_monthly") or 0),
                max_users=(int(included["max_users"]) if included.get("max_users") is not None else None),
                trial_days=int(included.get("trial_days") or 0),
                included_training_chars=int(included.get("training_chars") or 0),
            )
        return result

    def _addon_map(self) -> dict[str, BillingAddon]:
        result: dict[str, BillingAddon] = {}
        for row in self._repo.list_catalog():
            if row.entry_type != "addon":
                continue
            result[row.code] = BillingAddon(
                code=row.code,
                name=row.name,
                price_cents=int(row.price_cents or 0),
                metadata={**dict(row.included or {}), **dict(row.metadata_json or {})},
            )
        return result

    def _catalog_response(self) -> list[BillingCatalogEntryResponse]:
        return [
            BillingCatalogEntryResponse(
                entry_type=row.entry_type,
                code=row.code,
                name=row.name,
                currency=row.currency,
                price_cents=int(row.price_cents or 0),
                price=_money(int(row.price_cents or 0)),
                included=dict(row.included or {}),
                metadata=dict(row.metadata_json or {}),
            )
            for row in self._repo.list_catalog()
        ]

    def ensure_subscription(self, tenant) -> BillingSubscriptionORM:
        existing = self._repo.get_subscription(tenant.tenant_id)
        if existing is not None:
            return existing
        plan = self._plan_map()["free"]
        trial_started_at = getattr(tenant, "created_at", None) or self.clock.now()
        trial_ends_at = trial_started_at + timedelta(days=plan.trial_days)
        subscription = self._repo.upsert_subscription(
            tenant.tenant_id,
            plan_code="free",
            billing_period="monthly",
            status=SubscriptionStatus.TRIAL.value,
            trial_started_at=trial_started_at,
            trial_ends_at=trial_ends_at,
            carryover_training_chars=plan.included_training_chars,
        )
        self._sync_tenant_config(tenant, subscription)
        return subscription

    def set_signup_subscription(self, tenant_id: int, slug: str, *, plan_code: str, billing_period: str) -> None:
        plan = self._plan_map().get(plan_code) or self._plan_map()["free"]
        now = self.clock.now()
        status = SubscriptionStatus.TRIAL.value if plan.code == "free" else SubscriptionStatus.ACTIVE.value
        trial_ends_at = now + timedelta(days=plan.trial_days) if plan.trial_days else None
        sub = self._repo.upsert_subscription(
            tenant_id,
            plan_code=plan.code,
            billing_period=self._normalize_billing_period(billing_period),
            status=status,
            trial_started_at=now if plan.trial_days else None,
            trial_ends_at=trial_ends_at,
            carryover_training_chars=plan.included_training_chars,
        )
        tenant = self._tenant_repo.get_snapshot_by_slug(slug)
        if tenant is not None:
            self._sync_tenant_config(tenant, sub)

    def _normalize_billing_period(self, value: str | None) -> str:
        normalized = (value or "monthly").strip().lower()
        if normalized not in {"monthly", "quarterly", "yearly"}:
            return "monthly"
        return normalized

    def _sync_tenant_config(self, tenant, subscription: BillingSubscriptionORM) -> None:
        limits = self._build_limits(subscription)
        existing_cfg = self._tenant_repo.get_config_by_tenant_id(tenant.tenant_id, slug=tenant.slug)
        prev_flags = dict(existing_cfg.feature_flags or {}) if existing_cfg else {}
        merged_flags = {**prev_flags, "billing_enabled": True}
        self._tenant_repo.create_config(
            tenant.tenant_id,
            slug=tenant.slug,
            package=subscription.plan_code,
            feature_flags=merged_flags,
            limits=limits,
            created_by=None,
        )

    def _build_limits(self, subscription: BillingSubscriptionORM) -> dict[str, Any]:
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        return {
            "max_users": plan.max_users,
            "knowledge_bases": plan.included_kbs + int(subscription.extra_kb_count or 0),
            "storage_gb": plan.included_storage_gb + int(subscription.extra_storage_gb or 0),
            "questions_monthly": plan.included_questions_monthly,
            "addon_questions_carryover": int(subscription.carryover_addon_questions or 0),
            "training_chars_available": int(subscription.carryover_training_chars or 0),
            "trial_days": plan.trial_days,
        }

    def _load_resource_counts(self) -> dict[str, Any]:
        with self._sf() as db:
            user_count = db.query(UserORM).filter(UserORM.deleted_at.is_(None)).count()
            # Billing modulnak nincs közvetlen hozzáférése a knowledge ORM osztályhoz –
            # raw SQL COUNT-al számolunk (a session tenant-sémára van scoped-olva).
            kb_count = db.execute(text("SELECT COUNT(*) FROM knowledge_bases")).scalar() or 0
            return {
                "users": int(user_count or 0),
                "knowledge_bases": int(kb_count or 0),
            }

    def _current_period(self) -> tuple[str, datetime, datetime, date]:
        return _current_month_period(self.clock.now())

    def _question_usage_summary(self, tenant_id: int, subscription: BillingSubscriptionORM) -> tuple[dict[str, Any], list[BillingUserQuestionUsageResponse]]:
        period_key, _, _, _ = self._current_period()
        usage_rows = self._repo.list_question_usage(tenant_id, period_key)
        used_total = sum(int(row.question_count or 0) for row in usage_rows)
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        monthly_included = int(plan.included_questions_monthly or 0)
        addon_carryover = int(subscription.carryover_addon_questions or 0)
        available_total = monthly_included + addon_carryover
        remaining_included = max(0, monthly_included - used_total)
        consumed_from_addons = max(0, used_total - monthly_included)
        remaining_addons = max(0, addon_carryover - consumed_from_addons)
        percent = int(round((used_total / available_total) * 100)) if available_total > 0 else 100
        by_user = []
        with self._sf() as db:
            user_map = {int(row.id): row for row in db.query(UserORM).filter(UserORM.deleted_at.is_(None)).all()}
        for row in usage_rows:
            user = user_map.get(int(row.user_id))
            by_user.append(
                BillingUserQuestionUsageResponse(
                    user_id=int(row.user_id),
                    name=getattr(user, "name", None),
                    email=getattr(user, "email", "") or "",
                    question_count=int(row.question_count or 0),
                )
            )
        return (
            {
                "period_key": period_key,
                "used_total": used_total,
                "monthly_included": monthly_included,
                "remaining_included": remaining_included,
                "addon_carryover": addon_carryover,
                "remaining_addons": remaining_addons,
                "remaining_total": max(0, available_total - used_total),
                "available_total": available_total,
                "percent_used": max(0, min(100, percent)),
            },
            by_user,
        )

    def _training_usage_summary(self, tenant_id: int, subscription: BillingSubscriptionORM) -> dict[str, Any]:
        period_key, _, _, _ = self._current_period()
        training = self._repo.get_training_usage(tenant_id, period_key)
        trained_chars = int(getattr(training, "trained_chars", 0) or 0)
        storage_bytes = int(getattr(training, "storage_bytes", 0) or 0)
        available_chars = int(subscription.carryover_training_chars or 0)
        return {
            "period_key": period_key,
            "trained_chars": trained_chars,
            "remaining_training_chars": max(0, available_chars - trained_chars),
            "available_training_chars": available_chars,
            "storage_bytes": storage_bytes,
            "storage_gb_used_rounded": _round_storage_gb(storage_bytes),
        }

    def _invoice_to_response(self, row: BillingInvoiceORM) -> BillingInvoiceResponse:
        return BillingInvoiceResponse(
            invoice_type=row.invoice_type,
            period_key=row.period_key,
            status=row.status,
            currency=row.currency,
            total_cents=int(row.total_cents or 0),
            total=_money(int(row.total_cents or 0)),
            description=row.description or "",
            issued_at=row.issued_at,
            due_at=row.due_at,
            lines=list(row.lines or []),
        )

    def _estimate_next_invoice(self, subscription: BillingSubscriptionORM) -> dict[str, Any]:
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        _, _, period_end_dt, _ = self._current_period()
        period_multiplier = _billing_period_multiplier(subscription.billing_period)
        base_monthly_cents = _plan_monthly_charge_cents_after_discount(plan.price_cents, subscription.billing_period)
        recurring_addons_monthly_cents = (int(subscription.extra_kb_count or 0) * 500) + (int(subscription.extra_storage_gb or 0) * 500)
        base_cents = base_monthly_cents * period_multiplier
        recurring_addons_cents = recurring_addons_monthly_cents * period_multiplier
        total_cents = base_cents + recurring_addons_cents
        coverage_end = subscription.trial_ends_at.date() if subscription.plan_code == "free" and subscription.trial_ends_at is not None else period_end_dt.date()
        due_at = _charge_date_before_expiry(coverage_end)
        return {
            "currency": DEFAULT_CURRENCY,
            "discount_percent": _discount_percent(subscription.billing_period),
            "period_multiplier": period_multiplier,
            "base_plan_cents": base_cents,
            "recurring_addons_cents": recurring_addons_cents,
            "due_at_iso": due_at.isoformat(),
            "total_cents": total_cents,
            "total": _money(total_cents),
        }

    def get_overview(self, tenant) -> BillingOverviewResponse:
        subscription = self.ensure_subscription(tenant)
        self.process_due_cycles()
        subscription = self.ensure_subscription(tenant)
        subscription = self._restriction_use_case.sync_status(tenant, subscription)
        self._sync_tenant_config(tenant, subscription)
        question_usage, by_user = self._question_usage_summary(tenant.tenant_id, subscription)
        training_usage = self._training_usage_summary(tenant.tenant_id, subscription)
        resources = self._load_resource_counts()
        limits = self._build_limits(subscription)
        invoices = [self._invoice_to_response(row) for row in self._repo.list_recent_invoices(tenant.tenant_id)]
        period_key, period_start_dt, period_end_dt, _ = self._current_period()
        snapshot = self._tenant_repo.get_snapshot_by_slug(tenant.slug) if tenant.slug else None
        demo_mode = bool(snapshot and snapshot.config and snapshot.config.feature_flags and bool(snapshot.config.feature_flags.get("demo_mode")))
        return BillingOverviewResponse(
            current_period_key=period_key,
            current_period_start_iso=period_start_dt.date().isoformat(),
            current_period_end_iso=period_end_dt.date().isoformat(),
            catalog=self._catalog_response(),
            subscription={
                "plan_code": subscription.plan_code,
                "billing_period": subscription.billing_period,
                "status": subscription.status,
                "trial_ends_at": subscription.trial_ends_at,
                "scheduled_plan_code": subscription.scheduled_plan_code,
                "scheduled_billing_period": subscription.scheduled_billing_period,
                "scheduled_change_effective_period": subscription.scheduled_change_effective_period,
                "extra_kb_count": int(subscription.extra_kb_count or 0),
                "extra_storage_gb": int(subscription.extra_storage_gb or 0),
                "carryover_addon_questions": int(subscription.carryover_addon_questions or 0),
                "carryover_training_chars": int(subscription.carryover_training_chars or 0),
            },
            limits=limits,
            usage={
                "resources": resources,
                "questions": question_usage,
                "training": training_usage,
                "questions_by_user": [item.model_dump() for item in by_user],
            },
            invoices=invoices,
            estimated_next_invoice=self._estimate_next_invoice(subscription),
            demo_mode=demo_mode,
        )

    def _is_downgrade(self, current: BillingSubscriptionORM, next_plan_code: str) -> bool:
        plans = self._plan_map()
        current_plan = plans.get(current.plan_code) or plans["free"]
        next_plan = plans.get(next_plan_code) or plans["free"]
        return next_plan.price_cents < current_plan.price_cents or next_plan.included_kbs < current_plan.included_kbs or next_plan.included_storage_gb < current_plan.included_storage_gb

    @staticmethod
    def _proration_calendar_fraction(period_start: date, period_end_inclusive: date, today: date) -> tuple[int, int, float]:
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

    def _compute_upgrade_proration(self, subscription: BillingSubscriptionORM, normalized_plan: str, normalized_period: str) -> dict[str, Any] | None:
        plans = self._plan_map()
        if normalized_plan not in plans:
            return None
        if self._is_downgrade(subscription, normalized_plan):
            return None
        if subscription.plan_code == normalized_plan and subscription.billing_period == normalized_period:
            return None
        current_plan = plans.get(subscription.plan_code) or plans["free"]
        next_plan = plans[normalized_plan]
        old_m = _plan_monthly_charge_cents_after_discount(int(current_plan.price_cents), subscription.billing_period)
        new_m = _plan_monthly_charge_cents_after_discount(int(next_plan.price_cents), normalized_period)
        delta_m = max(0, new_m - old_m)
        _, ps, pe, _ = self._current_period()
        today = self.clock.now().date()
        total_d, rem_d, frac = self._proration_calendar_fraction(ps.date(), pe.date(), today)
        prorated = int(round(delta_m * rem_d / max(1, total_d)))
        prorated = max(0, prorated)
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
            "prorated_charge_cents": prorated,
            "currency": DEFAULT_CURRENCY,
        }

    def _apply_immediate_plan_change(self, tenant, subscription: BillingSubscriptionORM, normalized_plan: str, normalized_period: str) -> BillingSubscriptionORM:
        plans = self._plan_map()
        next_plan = plans[normalized_plan]
        carryover_training_chars = max(int(subscription.carryover_training_chars or 0), int(next_plan.included_training_chars or 0))
        updated = self._repo.upsert_subscription(
            tenant.tenant_id,
            plan_code=normalized_plan,
            billing_period=normalized_period,
            status=SubscriptionStatus.ACTIVE.value if normalized_plan != "free" else SubscriptionStatus.TRIAL.value,
            trial_started_at=subscription.trial_started_at if normalized_plan == "free" else None,
            trial_ends_at=subscription.trial_ends_at if normalized_plan == "free" else None,
            extra_kb_count=int(subscription.extra_kb_count or 0),
            extra_storage_gb=int(subscription.extra_storage_gb or 0),
            carryover_addon_questions=int(subscription.carryover_addon_questions or 0),
            carryover_training_chars=carryover_training_chars,
            scheduled_plan_code=None,
            scheduled_billing_period=None,
            scheduled_change_effective_period=None,
            question_warning_period_key=subscription.question_warning_period_key,
            question_warning_level=int(subscription.question_warning_level or 0),
        )
        self._sync_tenant_config(tenant, updated)
        return updated

    def get_upgrade_preview(self, tenant, *, plan_code: str, billing_period: str) -> BillingUpgradePreviewResponse:
        subscription = self.ensure_subscription(tenant)
        normalized_plan = (plan_code or "").strip().lower()
        normalized_period = self._normalize_billing_period(billing_period)
        if subscription.plan_code == "free":
            raise ValueError("Ingyenes csomagnál a szokásos előfizetési oldalon válasszon csomagot.")
        raw = self._compute_upgrade_proration(subscription, normalized_plan, normalized_period)
        if raw is None:
            raise ValueError("Ez a váltás nem kezelhető előnézetként (pl. csomagcsökkentés vagy nincs változás).")
        return BillingUpgradePreviewResponse(**raw)

    def complete_upgrade_after_checkout(self, tenant, *, plan_code: str, billing_period: str) -> BillingUpgradeCompleteResponse:
        subscription = self.ensure_subscription(tenant)
        normalized_plan = (plan_code or "").strip().lower()
        normalized_period = self._normalize_billing_period(billing_period)
        if normalized_plan not in self._plan_map():
            raise ValueError("Ismeretlen csomag.")
        if subscription.plan_code == "free":
            raise ValueError("Ingyenes csomagnál a szokásos előfizetési oldalon válasszon csomagot.")
        if self._is_downgrade(subscription, normalized_plan):
            raise ValueError("Csomagcsökkentés nem ezen az úton intézhető.")
        if subscription.plan_code == normalized_plan and subscription.billing_period == normalized_period:
            raise ValueError("Nincs változás.")
        preview = self._compute_upgrade_proration(subscription, normalized_plan, normalized_period)
        if preview is None:
            raise ValueError("Érvénytelen csomagváltás.")
        prorated = int(preview["prorated_charge_cents"])
        self._apply_immediate_plan_change(tenant, subscription, normalized_plan, normalized_period)
        if prorated > 0:
            next_plan = self._plan_map()[normalized_plan]
            self._repo.create_invoice(
                tenant.tenant_id,
                invoice_type="plan_upgrade_proration",
                period_key=f"{_utcnow():%Y-%m-%dT%H:%M:%S}",
                currency=DEFAULT_CURRENCY,
                total_cents=prorated,
                description=f"Időarányos csomagváltás: {next_plan.name}",
                lines=[
                    {
                        "code": "upgrade_proration",
                        "name": f"Időarányos díj ({preview['remaining_period_days']}/{preview['total_period_days']} nap)",
                        "quantity": 1,
                        "unit_price_cents": prorated,
                        "total_cents": prorated,
                        "simulated_payment": True,
                    }
                ],
                due_at=_utcnow(),
                status="simulated_paid",
            )
        return BillingUpgradeCompleteResponse(
            status="updated",
            prorated_charge_cents=prorated,
            prorated_charge=_money(prorated),
        )

    def update_subscription(self, tenant, *, plan_code: str, billing_period: str) -> dict[str, Any]:
        plans = self._plan_map()
        normalized_plan = (plan_code or "").strip().lower()
        if normalized_plan not in plans:
            raise ValueError("Ismeretlen csomag.")
        normalized_period = self._normalize_billing_period(billing_period)
        subscription = self.ensure_subscription(tenant)
        _, _, period_end_dt, _ = self._current_period()
        effective_period_key = f"{period_end_dt.year:04d}-{period_end_dt.month:02d}"
        if self._is_downgrade(subscription, normalized_plan):
            updated = self._repo.upsert_subscription(
                tenant.tenant_id,
                plan_code=subscription.plan_code,
                billing_period=subscription.billing_period,
                status=subscription.status,
                trial_started_at=subscription.trial_started_at,
                trial_ends_at=subscription.trial_ends_at,
                extra_kb_count=int(subscription.extra_kb_count or 0),
                extra_storage_gb=int(subscription.extra_storage_gb or 0),
                carryover_addon_questions=int(subscription.carryover_addon_questions or 0),
                carryover_training_chars=int(subscription.carryover_training_chars or 0),
                scheduled_plan_code=normalized_plan,
                scheduled_billing_period=normalized_period,
                scheduled_change_effective_period=effective_period_key,
                question_warning_period_key=subscription.question_warning_period_key,
                question_warning_level=int(subscription.question_warning_level or 0),
            )
            self._sync_tenant_config(tenant, updated)
            return {"status": "scheduled", "message": "A csomagcsökkentés a hónap végén lép életbe."}
        self._apply_immediate_plan_change(tenant, subscription, normalized_plan, normalized_period)
        return {"status": "updated", "message": "A csomag azonnal frissült."}

    def purchase_addon(self, tenant, *, addon_code: str, quantity: int) -> BillingInvoiceResponse:
        addons = self._addon_map()
        normalized_code = (addon_code or "").strip().lower()
        if normalized_code not in addons:
            raise ValueError("Ismeretlen addon.")
        qty = max(1, int(quantity or 1))
        addon = addons[normalized_code]
        subscription = self.ensure_subscription(tenant)
        extra_kb_count = int(subscription.extra_kb_count or 0)
        extra_storage_gb = int(subscription.extra_storage_gb or 0)
        carryover_addon_questions = int(subscription.carryover_addon_questions or 0)
        carryover_training_chars = int(subscription.carryover_training_chars or 0)
        if normalized_code == "question_pack_100":
            carryover_addon_questions += 100 * qty
        elif normalized_code == "question_pack_500":
            carryover_addon_questions += 500 * qty
        elif normalized_code == "extra_kb":
            extra_kb_count += qty
        elif normalized_code == "extra_storage_gb":
            extra_storage_gb += qty
        elif normalized_code in {"training_initial_500k", "training_extra_500k"}:
            carryover_training_chars += 500000 * qty
        updated = self._repo.upsert_subscription(
            tenant.tenant_id,
            plan_code=subscription.plan_code,
            billing_period=subscription.billing_period,
            status=subscription.status,
            trial_started_at=subscription.trial_started_at,
            trial_ends_at=subscription.trial_ends_at,
            extra_kb_count=extra_kb_count,
            extra_storage_gb=extra_storage_gb,
            carryover_addon_questions=carryover_addon_questions,
            carryover_training_chars=carryover_training_chars,
            scheduled_plan_code=subscription.scheduled_plan_code,
            scheduled_billing_period=subscription.scheduled_billing_period,
            scheduled_change_effective_period=subscription.scheduled_change_effective_period,
            question_warning_period_key=subscription.question_warning_period_key,
            question_warning_level=int(subscription.question_warning_level or 0),
        )
        self._sync_tenant_config(tenant, updated)
        invoice = self._repo.create_invoice(
            tenant.tenant_id,
            invoice_type=f"addon:{normalized_code}",
            period_key=f"{_utcnow():%Y-%m-%dT%H:%M:%S}",
            currency=DEFAULT_CURRENCY,
            total_cents=addon.price_cents * qty,
            description=f"{addon.name} x {qty}",
            lines=[
                {
                    "code": addon.code,
                    "name": addon.name,
                    "quantity": qty,
                    "unit_price_cents": addon.price_cents,
                    "total_cents": addon.price_cents * qty,
                    "simulated_payment": True,
                }
            ],
            due_at=_utcnow(),
            status="simulated_paid",
        )
        return self._invoice_to_response(invoice)

    def can_create_user(self, tenant) -> tuple[bool, str | None]:
        subscription = self.ensure_subscription(tenant)
        allowed, message = self._restriction_use_case.assert_not_restricted(tenant, subscription)
        if not allowed:
            return allowed, message
        limits = self._build_limits(subscription)
        max_users = limits.get("max_users")
        if max_users is None:
            return True, None
        resource_counts = self._load_resource_counts()
        if int(resource_counts["users"]) >= int(max_users):
            return False, f"Elérted a csomagban engedélyezett felhasználói limitet ({max_users})."
        return True, None

    def can_create_kb(self, tenant) -> tuple[bool, str | None]:
        subscription = self.ensure_subscription(tenant)
        allowed, message = self._restriction_use_case.assert_not_restricted(tenant, subscription)
        if not allowed:
            return allowed, message
        limits = self._build_limits(subscription)
        resource_counts = self._load_resource_counts()
        if int(resource_counts["knowledge_bases"]) >= int(limits["knowledge_bases"] or 0):
            return False, f"Elérted a tudástár limitet ({limits['knowledge_bases']})."
        return True, None

    def can_consume_question(self, tenant) -> tuple[bool, str | None]:
        if os.environ.get("BILLING_DISABLED", "").lower() in {"1", "true", "yes"}:
            return True, None
        subscription = self.ensure_subscription(tenant)
        allowed, message = self._restriction_use_case.assert_not_restricted(tenant, subscription)
        if not allowed:
            return allowed, message
        usage, _ = self._question_usage_summary(tenant.tenant_id, subscription)
        if int(usage["remaining_total"]) <= 0:
            return False, "Elfogyott a kérdésszám kereted. Vásárolj addon kérdéscsomagot."
        return True, None

    def can_consume_training_chars(self, tenant, char_count: int) -> tuple[bool, str | None]:
        if char_count <= 0:
            return True, None
        subscription = self.ensure_subscription(tenant)
        allowed, message = self._restriction_use_case.assert_not_restricted(tenant, subscription)
        if not allowed:
            return allowed, message
        training = self._training_usage_summary(tenant.tenant_id, subscription)
        remaining = int(training.get("remaining_training_chars") or 0)
        if remaining < char_count:
            return False, "Nincs elég tanítási karakterkeret a csomagban."
        return True, None

    def record_training_ingest(self, tenant, *, char_count: int, storage_bytes: int = 0) -> None:
        subscription = self.ensure_subscription(tenant)
        period_key, _, _, _ = self._current_period()
        self._repo.increment_training_usage(
            tenant.tenant_id,
            period_key,
            trained_chars=max(0, int(char_count)),
            storage_bytes=max(0, int(storage_bytes)),
        )

    def tenant_has_training_material(self, tenant) -> bool:
        subscription = self.ensure_subscription(tenant)
        training = self._training_usage_summary(tenant.tenant_id, subscription)
        return int(training.get("trained_chars") or 0) > 0 or int(training.get("storage_bytes") or 0) > 0

    def record_question(self, tenant, user_id: int) -> None:
        subscription = self.ensure_subscription(tenant)
        period_key, _, _, _ = self._current_period()
        self._repo.upsert_question_usage(tenant.tenant_id, user_id, period_key, increment=1)
        self._send_question_warning_if_needed(tenant, subscription)

    def _send_question_warning_if_needed(self, tenant, subscription: BillingSubscriptionORM) -> None:
        usage, _ = self._question_usage_summary(tenant.tenant_id, subscription)
        available_total = int(usage["available_total"] or 0)
        if available_total <= 0:
            return
        percent_used = int(usage["percent_used"] or 0)
        period_key = str(usage["period_key"])
        current_level = int(subscription.question_warning_level or 0) if subscription.question_warning_period_key == period_key else 0
        target_level = 0
        for level in QUESTION_WARNING_LEVELS:
            if percent_used >= level:
                target_level = level
        if target_level <= current_level:
            return
        owner = self._user_repository.get_owner()
        if owner is None or not getattr(owner, "email", None):
            return
        subject = "BrainBankCenter kérdéskeret figyelmeztetés"
        body = (
            f"A tenant ({tenant.slug}) elérte a kérdéskeret {target_level}%-át.\n\n"
            f"Aktuális időszak: {period_key}\n"
            f"Felhasznált kérdés: {usage['used_total']}\n"
            f"Elérhető összesen: {available_total}\n"
            f"Hátralévő kérdés: {usage['remaining_total']}\n"
        )
        self._email_service.send_email(owner.email, subject, body)
        self._repo.upsert_subscription(
            tenant.tenant_id,
            plan_code=subscription.plan_code,
            billing_period=subscription.billing_period,
            status=subscription.status,
            trial_started_at=subscription.trial_started_at,
            trial_ends_at=subscription.trial_ends_at,
            extra_kb_count=int(subscription.extra_kb_count or 0),
            extra_storage_gb=int(subscription.extra_storage_gb or 0),
            carryover_addon_questions=int(subscription.carryover_addon_questions or 0),
            carryover_training_chars=int(subscription.carryover_training_chars or 0),
            scheduled_plan_code=subscription.scheduled_plan_code,
            scheduled_billing_period=subscription.scheduled_billing_period,
            scheduled_change_effective_period=subscription.scheduled_change_effective_period,
            question_warning_period_key=period_key,
            question_warning_level=target_level,
        )

    def process_due_cycles(self) -> None:
        self._cycle_processor.process()


class BillingWorker:
    def __init__(self, poll_seconds: int = DEFAULT_POLL_SECONDS):
        self._poll_seconds = max(60, int(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
                service.process_due_cycles()
            except Exception:
                pass
            self._stop.wait(self._poll_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None


get_billing_service = service_dependency(PLATFORM_TENANT_USAGE_SERVICE)

router = APIRouter()


@router.get("/billing/overview", response_model=BillingOverviewResponse)
def get_billing_overview(
    tenant: RequiredTenantContextDep,
    svc: BillingService = Depends(get_billing_service),
    current_user: User = Depends(require_role("owner")),
):
    return svc.get_overview(tenant)


@router.patch("/billing/subscription")
def update_billing_subscription(
    tenant: RequiredTenantContextDep,
    body: BillingSubscriptionUpdateRequest = Body(...),
    svc: BillingService = Depends(get_billing_service),
    current_user: User = Depends(require_role("owner")),
):
    try:
        return svc.update_subscription(tenant, plan_code=body.plan_code, billing_period=body.billing_period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/billing/subscription/upgrade-preview", response_model=BillingUpgradePreviewResponse)
def billing_upgrade_preview(
    tenant: RequiredTenantContextDep,
    plan_code: str = Query(..., alias="plan_code"),
    billing_period: str = Query("monthly"),
    svc: BillingService = Depends(get_billing_service),
    current_user: User = Depends(require_role("owner")),
):
    try:
        return svc.get_upgrade_preview(tenant, plan_code=plan_code, billing_period=billing_period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/billing/subscription/upgrade-complete", response_model=BillingUpgradeCompleteResponse)
def billing_upgrade_complete(
    tenant: RequiredTenantContextDep,
    body: BillingSubscriptionUpdateRequest = Body(...),
    svc: BillingService = Depends(get_billing_service),
    current_user: User = Depends(require_role("owner")),
):
    try:
        return svc.complete_upgrade_after_checkout(tenant, plan_code=body.plan_code, billing_period=body.billing_period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/billing/addons/purchase", response_model=BillingInvoiceResponse)
def purchase_billing_addon(
    tenant: RequiredTenantContextDep,
    body: BillingAddonPurchaseRequest = Body(...),
    svc: BillingService = Depends(get_billing_service),
    current_user: User = Depends(require_role("owner")),
):
    try:
        return svc.purchase_addon(tenant, addon_code=body.addon_code, quantity=body.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _install_billing_tenant_schema(engine, slug: str) -> None:
    install_schema_tables(engine, slug, ())
    run_schema_statements(engine, slug, ())


def register_billing_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="billing_noop",
                install=_install_billing_tenant_schema,
                table_names=(),
            )
        ]
    )


__all__ = [
    "BillingAddonPurchaseRequest",
    "BillingCatalogEntryORM",
    "BillingInvoiceORM",
    "BillingQuestionUsageORM",
    "BillingRepository",
    "BillingService",
    "BillingSubscriptionORM",
    "BillingTrainingUsageORM",
    "BillingWorker",
    "get_billing_service",
    "register_billing_tenant_hooks",
    "router",
]
