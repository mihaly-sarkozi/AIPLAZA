# backend/apps/billing/service.py
# Feladat: A billing app központi application service rétege. Előfizetés lifecycle-t, catalogot, usage limiteket, upgrade/downgrade/proration logikát, számlázási ciklusokat, addon vásárlást, invoice PDF-et, access restrictiont és usage warning emailt kezel. Nagy blast radiusú program-specifikus számlázási üzleti logika.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from apps.billing.catalog import (
    addon_map_from_catalog,
    catalog_response_from_rows,
    default_catalog_rows,
    plan_map_from_catalog,
)
from apps.billing.calculations import (
    add_months_to_date as _add_months_to_date,
    billing_period_label_hu as _billing_period_label_hu,
    billing_period_multiplier as _billing_period_multiplier,
    charge_date_before_expiry as _charge_date_before_expiry,
    current_month_period as _current_month_period,
    discount_percent as _discount_percent,
    money as _money,
    plan_monthly_charge_cents_after_discount as _plan_monthly_charge_cents_after_discount,
    round_storage_gb as _round_storage_gb,
)
from apps.billing.debug_clock import BillingDebugClock
from apps.billing.domain import BillingAddon, BillingPlan
from apps.billing.models import (
    DEFAULT_CURRENCY,
    BillingCatalogEntryORM,
    BillingInvoiceORM,
    BillingQuestionUsageORM,
    BillingSubscriptionORM,
    BillingTrainingUsageORM,
)
from apps.billing.repositories import BillingRepository
from apps.billing.invoice_pdf import money_label, render_invoice_pdf_document
from apps.billing.payment import BillingPaymentGateway, PaymentExecutionResult
from apps.billing.subscription_proration import (
    compute_upgrade_proration,
    coverage_end_for_subscription,
    coverage_start_for_end,
    is_billing_period_downgrade,
    is_downgrade,
    is_scheduled_change,
    paid_until_after_upgrade,
    proration_calendar_fraction,
)
from apps.billing.workflows import (
    BillingCycleProcessor,
    InvoicingUseCase,
    RenewalUseCase,
    RestrictionUseCase,
    SubscriptionStateMachine,
    SubscriptionStatus,
)
from apps.billing.schemas import (
    BillingAccessStatusResponse,
    BillingCatalogEntryResponse,
    BillingDebugBillingRunResponse,
    BillingDebugDateResponse,
    BillingInvoiceResponse,
    BillingOverviewResponse,
    BillingUpgradeCompleteResponse,
    BillingUpgradePreviewResponse,
    BillingUserQuestionUsageResponse,
    TenantStatisticsResponse,
)
from core.modules.users.models.user_orm import UserORM
from core.kernel.interface.keys import PLATFORM_SETTINGS_SERVICE
from core.kernel.config.config_loader import settings
from core.modules.tenant.repositories import TenantRepository
from shared.utils.clock import Clock, SystemClock
from core.kernel.db.model_bases import AuthBase


DEFAULT_POLL_SECONDS = 3600
QUESTION_WARNING_LEVELS = (90, 100)
logger = logging.getLogger(__name__)


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
        self.clock = BillingDebugClock(clock or SystemClock())
        self._payment_gateway = BillingPaymentGateway()
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

    def _billing_provider(self) -> str:
        return self._get_payment_gateway().provider()

    def _is_simulated_provider(self) -> bool:
        return self._get_payment_gateway().is_simulated_provider()

    def _invoice_paid_status(self) -> str:
        return self._get_payment_gateway().invoice_paid_status()

    def _invoice_payment_method(self) -> str:
        return self._get_payment_gateway().invoice_payment_method()

    def _get_payment_gateway(self) -> BillingPaymentGateway:
        gateway = getattr(self, "_payment_gateway", None)
        if gateway is None:
            gateway = BillingPaymentGateway()
            self._payment_gateway = gateway
        return gateway

    def _execute_payment(
        self,
        *,
        amount_cents: int,
        description: str,
        metadata: dict[str, str] | None = None,
    ) -> PaymentExecutionResult:
        return self._get_payment_gateway().execute_payment(
            amount_cents=amount_cents,
            description=description,
            metadata=metadata,
        )

    def verify_payment_webhook_signature(self, *, payload: bytes, signature: str | None, secret: str | None) -> bool:
        return self._get_payment_gateway().verify_webhook_signature(
            payload=payload,
            signature=signature,
            secret=secret,
        )

    def ensure_storage(self) -> None:
        self._repo.ensure_storage()
        self._repo.seed_catalog(self._default_catalog_rows())
        try:
            self.clock.set_simulated_date(self._repo.get_debug_simulated_date())
        except Exception:
            logger.exception("Failed to load persisted simulated billing date during storage initialization")

    def set_debug_simulated_date(self, value: date | None) -> BillingDebugDateResponse:
        try:
            self._repo.set_debug_simulated_date(value)
        except Exception:
            logger.exception("Failed to persist simulated billing date")
        self.clock.set_simulated_date(value)
        self.process_due_cycles()
        return self.get_debug_simulated_date()

    def get_debug_simulated_date(self) -> BillingDebugDateResponse:
        simulated = self.clock.simulated_date
        try:
            persisted = self._repo.get_debug_simulated_date()
            if persisted != simulated:
                self.clock.set_simulated_date(persisted)
                simulated = persisted
        except Exception:
            logger.exception("Failed to load persisted simulated billing date")
        return BillingDebugDateResponse(
            enabled=True,
            simulated_date=simulated.isoformat() if simulated is not None else None,
            current_date=self.clock.now().date().isoformat(),
        )

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
        return default_catalog_rows()

    def _plan_map(self) -> dict[str, BillingPlan]:
        return plan_map_from_catalog(self._repo.list_catalog())

    def _addon_map(self) -> dict[str, BillingAddon]:
        return addon_map_from_catalog(self._repo.list_catalog())

    def _catalog_response(self) -> list[BillingCatalogEntryResponse]:
        return catalog_response_from_rows(self._repo.list_catalog())

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

    @staticmethod
    def _subscription_state_payload(subscription: BillingSubscriptionORM) -> dict[str, Any]:
        return {
            "plan_code": subscription.plan_code,
            "billing_period": subscription.billing_period,
            "status": subscription.status,
            "trial_started_at": subscription.trial_started_at,
            "trial_ends_at": subscription.trial_ends_at,
            "extra_kb_count": int(subscription.extra_kb_count or 0),
            "extra_storage_gb": int(subscription.extra_storage_gb or 0),
            "carryover_addon_questions": int(subscription.carryover_addon_questions or 0),
            "carryover_training_chars": int(subscription.carryover_training_chars or 0),
            "scheduled_plan_code": subscription.scheduled_plan_code,
            "scheduled_billing_period": subscription.scheduled_billing_period,
            "scheduled_change_effective_period": subscription.scheduled_change_effective_period,
            "question_warning_period_key": subscription.question_warning_period_key,
            "question_warning_level": int(subscription.question_warning_level or 0),
        }

    def _upsert_subscription_from_existing(
        self,
        tenant_id: int,
        subscription: BillingSubscriptionORM,
        **overrides: Any,
    ) -> BillingSubscriptionORM:
        payload = self._subscription_state_payload(subscription)
        payload.update(overrides)
        return self._repo.upsert_subscription(tenant_id, **payload)

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

    def _available_training_chars(self, subscription: BillingSubscriptionORM) -> int:
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        invoice_addon_chars = self._training_addon_invoice_chars(int(subscription.tenant_id))
        return max(
            max(0, int(plan.included_training_chars or 0)),
            max(0, int(subscription.carryover_training_chars or 0)),
            max(0, int(plan.included_training_chars or 0)) + invoice_addon_chars,
        )

    def _training_addon_invoice_chars(self, tenant_id: int) -> int:
        addons = self._addon_map()
        total = 0
        for invoice in self._repo.list_training_addon_invoices(tenant_id):
            for line in list(invoice.lines or []):
                if not isinstance(line, dict):
                    continue
                code = str(line.get("code") or "").strip()
                if code not in {"training_initial_500k", "training_extra_500k"}:
                    continue
                addon = addons.get(code)
                chars = int((addon.metadata if addon else {}).get("training_chars") or 500000)
                quantity = max(1, int(line.get("quantity") or 1))
                total += max(0, chars) * quantity
        return total

    def _build_limits(self, subscription: BillingSubscriptionORM) -> dict[str, Any]:
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        return {
            "max_users": plan.max_users,
            "knowledge_bases": plan.included_kbs + int(subscription.extra_kb_count or 0),
            "storage_gb": plan.included_storage_gb + int(subscription.extra_storage_gb or 0),
            "questions_monthly": plan.included_questions_monthly,
            "addon_questions_carryover": int(subscription.carryover_addon_questions or 0),
            "training_chars_available": self._available_training_chars(subscription),
            "trial_days": plan.trial_days,
        }

    def _required_extra_storage_gb(
        self,
        subscription: BillingSubscriptionORM,
        resources: dict[str, Any] | None = None,
    ) -> int:
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        usage = resources if resources is not None else self._load_resource_counts()
        used_gb = max(0, int(usage.get("storage_gb_used_rounded") or 0))
        return max(0, used_gb - int(plan.included_storage_gb or 0))

    def _load_resource_counts(self) -> dict[str, Any]:
        with self._sf() as db:
            user_count = db.query(UserORM).filter(UserORM.deleted_at.is_(None)).count()
            # Billing modulnak nincs közvetlen hozzáférése a knowledge ORM osztályhoz –
            # raw SQL COUNT-al számolunk (a session tenant-sémára van scoped-olva).
            schema = db.execute(text("select current_schema()")).scalar_one()

            def table_exists(table_name: str) -> bool:
                return bool(
                    db.execute(
                        text(
                            """
                            select 1
                            from information_schema.tables
                            where table_schema = :schema and table_name = :table_name
                            """
                        ),
                        {"schema": schema, "table_name": table_name},
                    ).scalar_one_or_none()
                )

            def column_exists(table_name: str, column_name: str) -> bool:
                return bool(
                    db.execute(
                        text(
                            """
                            select 1
                            from information_schema.columns
                            where table_schema = :schema and table_name = :table_name and column_name = :column_name
                            """
                        ),
                        {"schema": schema, "table_name": table_name, "column_name": column_name},
                    ).scalar_one_or_none()
                )

            has_kb_table = table_exists("knowledge_bases")
            has_deleted_at = has_kb_table and column_exists("knowledge_bases", "deleted_at")
            kb_where = "WHERE deleted_at IS NULL" if has_deleted_at else ""
            kb_count = (
                db.execute(text(f"SELECT COUNT(*) FROM knowledge_bases {kb_where}")).scalar() or 0
                if has_kb_table
                else 0
            )
            storage_bytes = 0
            if (
                has_kb_table
                and table_exists("knowledge_ingest_inputs")
                and table_exists("knowledge_ingest_items")
            ):
                deleted_filter = "WHERE kb.deleted_at IS NULL" if has_deleted_at else ""
                storage_bytes = db.execute(
                    text(
                        f"""
                        SELECT COALESCE(SUM(COALESCE(inp.size_bytes, 0)), 0)
                        FROM knowledge_ingest_inputs inp
                        JOIN knowledge_ingest_items item ON item.id = inp.ingest_item_id
                        JOIN knowledge_bases kb ON kb.uuid = item.corpus_uuid
                        {deleted_filter}
                        """
                    )
                ).scalar() or 0
            return {
                "users": int(user_count or 0),
                "knowledge_bases": int(kb_count or 0),
                "storage_bytes": int(storage_bytes or 0),
                "storage_gb_used_rounded": _round_storage_gb(int(storage_bytes or 0)),
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
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        included_chars = max(0, int(plan.included_training_chars or 0))
        available_chars = self._available_training_chars(subscription)
        addon_chars = max(0, available_chars - included_chars)
        return {
            "period_key": period_key,
            "trained_chars": trained_chars,
            "remaining_training_chars": max(0, available_chars - trained_chars),
            "available_training_chars": available_chars,
            "included_training_chars": included_chars,
            "addon_training_chars": addon_chars,
            "storage_bytes": storage_bytes,
            "storage_gb_used_rounded": _round_storage_gb(storage_bytes),
        }

    def _invoice_to_response(self, row: BillingInvoiceORM) -> BillingInvoiceResponse:
        return BillingInvoiceResponse(
            id=int(row.id),
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

    @staticmethod
    def _date_from_invoice_value(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw.split("T", 1)[0])
        except ValueError:
            return None

    def _coverage_date_from_invoice(self, invoice: BillingInvoiceORM | None) -> date | None:
        if invoice is None:
            return None
        for line in list(invoice.lines or []):
            if not isinstance(line, dict):
                continue
            for key in ("next_billing_date", "paid_until_iso"):
                parsed = self._date_from_invoice_value(line.get(key))
                if parsed is not None:
                    return parsed
        return None

    def _subscription_anchor_due_date(self, subscription: BillingSubscriptionORM) -> date | None:
        anchor = subscription.trial_started_at or subscription.created_at
        if anchor is None:
            return None
        return _add_months_to_date(anchor.date(), _billing_period_multiplier(subscription.billing_period))

    def _subscription_due_date(self, tenant_id: int, subscription: BillingSubscriptionORM, fallback_date: date) -> date:
        paid = self._repo.get_latest_invoice_for_type(tenant_id, "monthly_subscription")
        if subscription.trial_ends_at is not None:
            return subscription.trial_ends_at.date()
        invoice_coverage_end = self._coverage_date_from_invoice(paid)
        if invoice_coverage_end is not None:
            return invoice_coverage_end
        if paid is not None and paid.issued_at is not None:
            return _add_months_to_date(paid.issued_at.date(), _billing_period_multiplier(subscription.billing_period))
        anchor_due_date = self._subscription_anchor_due_date(subscription)
        if anchor_due_date is not None:
            return anchor_due_date
        return fallback_date

    def _estimate_next_invoice(
        self,
        subscription: BillingSubscriptionORM,
        resources: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        _, _, period_end_dt, _ = self._current_period()
        period_multiplier = _billing_period_multiplier(subscription.billing_period)
        base_monthly_cents = _plan_monthly_charge_cents_after_discount(plan.price_cents, subscription.billing_period)
        next_extra_storage_gb = self._required_extra_storage_gb(subscription, resources)
        recurring_addons_monthly_cents = (int(subscription.extra_kb_count or 0) * 500) + (next_extra_storage_gb * 500)
        base_cents = base_monthly_cents * period_multiplier
        recurring_addons_cents = recurring_addons_monthly_cents * period_multiplier
        total_cents = base_cents + recurring_addons_cents
        due_at = self._subscription_due_date(int(subscription.tenant_id), subscription, period_end_dt.date())
        return {
            "currency": DEFAULT_CURRENCY,
            "discount_percent": _discount_percent(subscription.billing_period),
            "period_multiplier": period_multiplier,
            "base_plan_cents": base_cents,
            "recurring_addons_cents": recurring_addons_cents,
            "next_extra_storage_gb": next_extra_storage_gb,
            "current_extra_storage_gb": int(subscription.extra_storage_gb or 0),
            "due_at_iso": due_at.isoformat(),
            "total_cents": total_cents,
            "total": _money(total_cents),
        }

    @staticmethod
    def _subscription_period_key(billing_date: date) -> str:
        return billing_date.isoformat()

    def _billing_due_date(self, subscription: BillingSubscriptionORM, fallback_date: date) -> date:
        if subscription.trial_ends_at is not None:
            return subscription.trial_ends_at.date()
        anchor_due_date = self._subscription_anchor_due_date(subscription)
        if anchor_due_date is not None:
            return anchor_due_date
        return fallback_date

    def _next_billing_date_after(self, billing_date: date, billing_period: str) -> date:
        return _add_months_to_date(billing_date, _billing_period_multiplier(billing_period))

    def _payment_warning(self, tenant_id: int) -> dict[str, Any] | None:
        failed = self._repo.get_latest_invoice_for_type(tenant_id, "monthly_subscription_failed")
        if failed is None or failed.status != "payment_failed":
            return None
        paid = self._repo.get_latest_invoice_for_type(tenant_id, "monthly_subscription")
        if paid is not None and paid.issued_at is not None and failed.issued_at is not None:
            try:
                if paid.issued_at > failed.issued_at:
                    return None
            except TypeError:
                if paid.issued_at.replace(tzinfo=None) > failed.issued_at.replace(tzinfo=None):
                    return None
        due_at = failed.due_at
        if due_at is None:
            return None
        return {
            "status": "payment_failed",
            "failed_at_iso": failed.issued_at.date().isoformat() if failed.issued_at else None,
            "grace_until_iso": due_at.date().isoformat(),
            "is_expired": self.clock.now().date() > due_at.date(),
            "message": "Nem volt sikeres a fizetés. A türelmi idő lejárta után a rendszer korlátozott módba kerül.",
        }

    def _billing_payment_notice(self, tenant_id: int, subscription: BillingSubscriptionORM) -> dict[str, Any] | None:
        failed_notice = self._payment_warning(tenant_id)
        if failed_notice is not None:
            return failed_notice
        if subscription.plan_code == "free":
            return None
        estimated = self._estimate_next_invoice(subscription)
        due_raw = str(estimated.get("due_at_iso") or "")
        if not due_raw:
            return None
        try:
            due_date = date.fromisoformat(due_raw)
        except ValueError:
            return None
        today = self.clock.now().date()
        if today <= due_date:
            return None
        grace_until = due_date + timedelta(days=5)
        return {
            "status": "payment_overdue",
            "failed_at_iso": due_date.isoformat(),
            "grace_until_iso": grace_until.isoformat(),
            "is_expired": today > grace_until,
            "message": "A számla esedékessége lejárt. A türelmi idő lejárta után a rendszer korlátozott módba kerül.",
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
        paid_until_date = self._subscription_due_date(tenant.tenant_id, subscription, period_end_dt.date())
        snapshot = self._tenant_repo.get_snapshot_by_slug(tenant.slug) if tenant.slug else None
        demo_mode = bool(snapshot and snapshot.config and snapshot.config.feature_flags and bool(snapshot.config.feature_flags.get("demo_mode")))
        return BillingOverviewResponse(
            current_period_key=period_key,
            current_period_start_iso=period_start_dt.date().isoformat(),
            current_period_end_iso=paid_until_date.isoformat(),
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
            estimated_next_invoice=self._estimate_next_invoice(subscription, resources),
            payment_warning=self._billing_payment_notice(tenant.tenant_id, subscription),
            demo_mode=demo_mode,
        )

    def _query_statistics(self) -> dict[str, Any]:
        try:
            with self._sf() as db:
                summary = db.execute(
                    text(
                        """
                        SELECT
                            COUNT(id) AS total,
                            AVG(latency_ms) AS avg_latency,
                            MAX(created_at) AS last_query_at
                        FROM knowledge_query_runs
                        """
                    )
                ).mappings().one()
                total = int(summary["total"] or 0)
                avg_latency = float(summary["avg_latency"] or 0.0)
                last_query_at = summary["last_query_at"]
                by_corpus_rows = db.execute(
                    text(
                        """
                        SELECT
                            corpus_uuid,
                            COUNT(id) AS query_count,
                            AVG(latency_ms) AS avg_latency,
                            MAX(created_at) AS last_query_at
                        FROM knowledge_query_runs
                        GROUP BY corpus_uuid
                        ORDER BY COUNT(id) DESC
                        """
                    )
                ).mappings().all()
                recent_rows = db.execute(
                    text(
                        """
                        SELECT id, query_text, corpus_uuid, latency_ms, result_count, feedback, created_at
                        FROM knowledge_query_runs
                        ORDER BY created_at DESC
                        LIMIT 20
                        """
                    )
                ).mappings().all()
            return {
                "total": total,
                "avg_latency_ms": round(avg_latency, 2),
                "last_query_at": last_query_at,
                "by_corpus": [
                    {
                        "corpus_uuid": row["corpus_uuid"],
                        "query_count": int(row["query_count"] or 0),
                        "avg_latency_ms": round(float(row["avg_latency"] or 0.0), 2),
                        "last_query_at": row["last_query_at"],
                    }
                    for row in by_corpus_rows
                ],
                "recent": [
                    {
                        "id": row["id"],
                        "query_text": row["query_text"],
                        "corpus_uuid": row["corpus_uuid"],
                        "latency_ms": round(float(row["latency_ms"] or 0.0), 2),
                        "result_count": int(row["result_count"] or 0),
                        "feedback": row["feedback"],
                        "created_at": row["created_at"],
                    }
                    for row in recent_rows
                ],
            }
        except SQLAlchemyError:
            return {"total": 0, "avg_latency_ms": 0, "last_query_at": None, "by_corpus": [], "recent": []}

    def _ingest_statistics(self) -> dict[str, Any]:
        try:
            with self._sf() as db:
                aggregates = db.execute(
                    text(
                        """
                        SELECT
                            COUNT(id) AS total_runs,
                            COALESCE(SUM(batch_size), 0) AS total_items,
                            COALESCE(SUM(completed_count), 0) AS completed_items,
                            COALESCE(SUM(failed_count), 0) AS failed_items,
                            COALESCE(SUM(duplicate_count), 0) AS duplicate_items,
                            COALESCE(SUM(rejected_count), 0) AS rejected_items,
                            MAX(completed_at) AS last_completed_at
                        FROM knowledge_ingest_runs
                        """
                    )
                ).mappings().one()
                by_status_rows = db.execute(
                    text(
                        """
                        SELECT status, COUNT(id) AS count
                        FROM knowledge_ingest_runs
                        GROUP BY status
                        ORDER BY COUNT(id) DESC
                        """
                    )
                ).mappings().all()
                by_corpus_rows = db.execute(
                    text(
                        """
                        SELECT
                            corpus_uuid,
                            COUNT(id) AS run_count,
                            COALESCE(SUM(completed_count), 0) AS completed_items,
                            COALESCE(SUM(failed_count), 0) AS failed_items,
                            MAX(updated_at) AS last_updated_at
                        FROM knowledge_ingest_runs
                        GROUP BY corpus_uuid
                        ORDER BY MAX(updated_at) DESC
                        """
                    )
                ).mappings().all()
                recent_rows = db.execute(
                    text(
                        """
                        SELECT id, corpus_uuid, input_channel, status, batch_size, completed_count, failed_count, created_at, completed_at
                        FROM knowledge_ingest_runs
                        ORDER BY created_at DESC
                        LIMIT 20
                        """
                    )
                ).mappings().all()
            return {
                "total_runs": int(aggregates["total_runs"] or 0),
                "total_items": int(aggregates["total_items"] or 0),
                "completed_items": int(aggregates["completed_items"] or 0),
                "failed_items": int(aggregates["failed_items"] or 0),
                "duplicate_items": int(aggregates["duplicate_items"] or 0),
                "rejected_items": int(aggregates["rejected_items"] or 0),
                "last_completed_at": aggregates["last_completed_at"],
                "by_status": [{"status": row["status"], "count": int(row["count"] or 0)} for row in by_status_rows],
                "by_corpus": [
                    {
                        "corpus_uuid": row["corpus_uuid"],
                        "run_count": int(row["run_count"] or 0),
                        "completed_items": int(row["completed_items"] or 0),
                        "failed_items": int(row["failed_items"] or 0),
                        "last_updated_at": row["last_updated_at"],
                    }
                    for row in by_corpus_rows
                ],
                "recent": [
                    {
                        "id": row["id"],
                        "corpus_uuid": row["corpus_uuid"],
                        "input_channel": row["input_channel"],
                        "status": row["status"],
                        "batch_size": int(row["batch_size"] or 0),
                        "completed_count": int(row["completed_count"] or 0),
                        "failed_count": int(row["failed_count"] or 0),
                        "created_at": row["created_at"],
                        "completed_at": row["completed_at"],
                    }
                    for row in recent_rows
                ],
            }
        except SQLAlchemyError:
            return {
                "total_runs": 0,
                "total_items": 0,
                "completed_items": 0,
                "failed_items": 0,
                "duplicate_items": 0,
                "rejected_items": 0,
                "last_completed_at": None,
                "by_status": [],
                "by_corpus": [],
                "recent": [],
            }

    def _domain_statistics(self, tenant_id: int, slug: str) -> dict[str, Any]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            rows = db.execute(
                text(
                    """
                    SELECT id, domain, verified_at, created_at
                    FROM public.tenant_domains
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC, domain ASC
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().all()
        primary_domain = f"{slug}.{settings.tenant_base_domain}" if slug and settings.tenant_base_domain else slug
        items = [
            {
                "id": row["id"],
                "domain": row["domain"],
                "verified": row["verified_at"] is not None,
                "verified_at": row["verified_at"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        return {
            "primary_domain": primary_domain,
            "total": len(items),
            "verified": sum(1 for item in items if item["verified"]),
            "items": items,
        }

    def get_tenant_statistics(self, tenant) -> TenantStatisticsResponse:
        overview = self.get_overview(tenant)
        subscription = dict(overview.subscription)
        package_code = str(subscription.get("plan_code") or "free")
        plan = next((item for item in overview.catalog if item.code == package_code and item.entry_type == "plan"), None)
        queries = self._query_statistics()
        training_runs = self._ingest_statistics()
        domains = self._domain_statistics(tenant.tenant_id, tenant.slug)
        usage = dict(overview.usage)
        question_usage = dict(usage.get("questions") or {})
        training_usage = dict(usage.get("training") or {})
        resources = dict(usage.get("resources") or {})
        summary = {
            "query_count": int(question_usage.get("used_total") or queries.get("total") or 0),
            "query_limit": int(question_usage.get("available_total") or 0),
            "training_runs": int(training_runs.get("total_runs") or 0),
            "trained_chars": int(training_usage.get("trained_chars") or 0),
            "training_char_limit": int(training_usage.get("available_training_chars") or 0),
            "storage_bytes": int(resources.get("storage_bytes") or training_usage.get("storage_bytes") or 0),
            "knowledge_bases": int(resources.get("knowledge_bases") or 0),
            "users": int(resources.get("users") or 0),
            "domains": int(domains.get("total") or 0),
            "verified_domains": int(domains.get("verified") or 0),
            "package_code": package_code,
            "package_status": subscription.get("status"),
        }
        return TenantStatisticsResponse(
            period={
                "key": overview.current_period_key,
                "start_iso": overview.current_period_start_iso,
                "end_iso": overview.current_period_end_iso,
            },
            summary=summary,
            queries={
                **queries,
                "billing": question_usage,
                "by_user": usage.get("questions_by_user") or [],
            },
            usage={
                "resources": resources,
                "questions": question_usage,
                "training": training_usage,
            },
            training={
                **training_runs,
                "billing": training_usage,
            },
            domains=domains,
            package={
                "subscription": subscription,
                "limits": overview.limits,
                "plan": plan.model_dump() if plan else None,
                "estimated_next_invoice": overview.estimated_next_invoice,
                "payment_warning": overview.payment_warning,
                "demo_mode": overview.demo_mode,
            },
        )

    def get_access_status(self, tenant) -> BillingAccessStatusResponse:
        subscription = self.ensure_subscription(tenant)
        self.process_due_cycles()
        subscription = self.ensure_subscription(tenant)
        subscription = self._restriction_use_case.sync_status(tenant, subscription)
        self._sync_tenant_config(tenant, subscription)
        return BillingAccessStatusResponse(
            restricted=subscription.status == SubscriptionStatus.RESTRICTED.value,
            payment_warning=self._billing_payment_notice(tenant.tenant_id, subscription),
        )

    def _billing_profile_snapshot(self) -> dict[str, str]:
        try:
            settings_service = get_service(PLATFORM_SETTINGS_SERVICE)
            if hasattr(settings_service, "get_billing_profile"):
                return dict(settings_service.get_billing_profile())
            snapshot = settings_service.get_settings_snapshot()
            return {
                "billing_company_name": str(snapshot.get("billing_company_name") or ""),
                "billing_tax_id": str(snapshot.get("billing_tax_id") or ""),
                "billing_address_line": str(snapshot.get("billing_address_line") or ""),
                "billing_postal_code": str(snapshot.get("billing_postal_code") or ""),
                "billing_city": str(snapshot.get("billing_city") or ""),
                "billing_region": str(snapshot.get("billing_region") or ""),
                "billing_country": str(snapshot.get("billing_country") or ""),
            }
        except Exception:
            return {}

    @staticmethod
    def _money_label(cents: int) -> str:
        return money_label(cents)

    def render_invoice_pdf(self, tenant, invoice_id: int) -> tuple[bytes, str]:
        invoice = self._repo.get_invoice_by_id(tenant.tenant_id, invoice_id)
        if invoice is None:
            raise ValueError("Számla nem található.")
        issuer = {
            "name": settings.invoice_issuer_name,
            "tax_id": settings.invoice_issuer_tax_id,
            "address_line": settings.invoice_issuer_address_line,
            "postal_code": settings.invoice_issuer_postal_code,
            "city": settings.invoice_issuer_city,
            "region": settings.invoice_issuer_region,
            "country": settings.invoice_issuer_country,
            "phone": settings.invoice_issuer_phone,
            "website": settings.invoice_issuer_website,
            "email": settings.invoice_issuer_email,
        }
        return render_invoice_pdf_document(
            tenant=tenant,
            invoice=invoice,
            issuer=issuer,
            buyer=self._billing_profile_snapshot(),
        )

    def _is_downgrade(self, current: BillingSubscriptionORM, next_plan_code: str) -> bool:
        return is_downgrade(current=current, next_plan_code=next_plan_code, plans=self._plan_map())

    @staticmethod
    def _is_billing_period_downgrade(current_period: str, next_period: str) -> bool:
        return is_billing_period_downgrade(current_period, next_period)

    def _is_scheduled_change(self, current: BillingSubscriptionORM, next_plan_code: str, next_period: str) -> bool:
        return is_scheduled_change(
            current=current,
            next_plan_code=next_plan_code,
            next_period=next_period,
            plans=self._plan_map(),
        )

    @staticmethod
    def _proration_calendar_fraction(period_start: date, period_end_inclusive: date, today: date) -> tuple[int, int, float]:
        return proration_calendar_fraction(period_start, period_end_inclusive, today)

    def _coverage_end_for_subscription(self, subscription: BillingSubscriptionORM, fallback_period_end: date) -> date:
        return coverage_end_for_subscription(subscription, fallback_period_end)

    def _coverage_start_for_end(self, period_end: date, normalized_period: str) -> date:
        return coverage_start_for_end(period_end, normalized_period)

    def _paid_until_after_upgrade(self, upgrade_date: date, normalized_period: str) -> date:
        return paid_until_after_upgrade(upgrade_date, normalized_period)

    def _compute_upgrade_proration(self, subscription: BillingSubscriptionORM, normalized_plan: str, normalized_period: str) -> dict[str, Any] | None:
        _, _, pe, _ = self._current_period()
        return compute_upgrade_proration(
            subscription=subscription,
            normalized_plan=normalized_plan,
            normalized_period=normalized_period,
            plans=self._plan_map(),
            period_end=pe.date(),
            today=self.clock.now().date(),
        )

    def _apply_immediate_plan_change(
        self,
        tenant,
        subscription: BillingSubscriptionORM,
        normalized_plan: str,
        normalized_period: str,
        *,
        paid_until: datetime | None = None,
    ) -> BillingSubscriptionORM:
        plans = self._plan_map()
        next_plan = plans[normalized_plan]
        carryover_training_chars = max(int(subscription.carryover_training_chars or 0), int(next_plan.included_training_chars or 0))
        updated = self._upsert_subscription_from_existing(
            tenant.tenant_id,
            subscription,
            plan_code=normalized_plan,
            billing_period=normalized_period,
            status=SubscriptionStatus.ACTIVE.value if normalized_plan != "free" else SubscriptionStatus.TRIAL.value,
            trial_started_at=subscription.trial_started_at if normalized_plan == "free" else None,
            trial_ends_at=subscription.trial_ends_at if normalized_plan == "free" else paid_until,
            carryover_training_chars=carryover_training_chars,
            scheduled_plan_code=None,
            scheduled_billing_period=None,
            scheduled_change_effective_period=None,
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

    @staticmethod
    def _is_verified_payment_status(status: str | None) -> bool:
        return str(status or "").strip().lower() in {"paid", "manual_paid", "simulated_paid"}

    def _latest_verified_upgrade_invoice(
        self,
        *,
        tenant_id: int,
        target_plan: str,
        target_period: str,
    ) -> BillingInvoiceORM | None:
        for invoice in self._repo.list_recent_invoices(tenant_id, limit=100):
            if invoice.invoice_type != "plan_upgrade":
                continue
            if not self._is_verified_payment_status(invoice.status):
                continue
            for line in list(invoice.lines or []):
                if not isinstance(line, dict):
                    continue
                if str(line.get("code") or "") != "upgrade_new_period":
                    continue
                if str(line.get("target_plan_code") or "") != target_plan:
                    continue
                if str(line.get("billing_period") or "") != target_period:
                    continue
                return invoice
        return None

    def process_verified_payment_event(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_provider = (provider or "").strip().lower()
        normalized_event_id = (event_id or "").strip()
        normalized_event_type = (event_type or "").strip().lower()
        if not normalized_provider or not normalized_event_id:
            raise ValueError("Hiányzó payment event azonosító.")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        tenant_id = int(metadata.get("tenant_id") or payload.get("tenant_id") or 0)
        if tenant_id <= 0:
            raise ValueError("Hiányzó tenant azonosító a payment eventben.")
        event, is_new = self._repo.record_payment_event_once(
            provider=normalized_provider,
            event_id=normalized_event_id,
            event_type=normalized_event_type,
            tenant_id=tenant_id,
            payload=payload,
        )
        if not is_new:
            return {"status": "duplicate", "event_id": event.event_id}
        flow = str(metadata.get("flow") or payload.get("flow") or "").strip().lower()
        if flow != "plan_upgrade" or normalized_event_type not in {"checkout.session.completed", "invoice.paid", "payment.succeeded"}:
            return {"status": "recorded", "event_id": event.event_id}
        target_plan = str(metadata.get("target_plan") or metadata.get("to_plan") or "").strip().lower()
        target_period = self._normalize_billing_period(str(metadata.get("billing_period") or "monthly"))
        tenant = self._tenant_repo.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError("Ismeretlen tenant.")
        if not hasattr(tenant, "tenant_id"):
            tenant = SimpleNamespace(
                tenant_id=tenant_id,
                slug=getattr(tenant, "slug", ""),
                name=getattr(tenant, "name", ""),
                created_at=getattr(tenant, "created_at", None),
            )
        subscription = self.ensure_subscription(tenant)
        preview = self._compute_upgrade_proration(subscription, target_plan, target_period)
        if preview is None:
            raise ValueError("Érvénytelen webhook upgrade payload.")
        paid_until = date.fromisoformat(str(preview["paid_until_iso"]))
        self._apply_immediate_plan_change(
            tenant,
            subscription,
            target_plan,
            target_period,
            paid_until=datetime.combine(paid_until, datetime.min.time(), tzinfo=UTC),
        )
        issued_at = self.clock.now()
        next_plan = self._plan_map()[target_plan]
        total_charge = int(metadata.get("amount_cents") or payload.get("amount_cents") or preview["total_charge_cents"])
        period_key = f"pe{int(event.id):014d}"[:16]
        if self._repo.get_invoice(tenant_id, "plan_upgrade", period_key) is None:
            self._repo.create_invoice(
                tenant_id,
                invoice_type="plan_upgrade",
                period_key=period_key,
                currency=DEFAULT_CURRENCY,
                total_cents=total_charge,
                description=f"Webhook verified csomagváltás: {next_plan.name}",
                lines=[
                    {
                        "code": "upgrade_new_period",
                        "name": f"Új csomag teljes díja ({self._billing_period_label(target_period)})",
                        "target_plan_code": target_plan,
                        "billing_period": target_period,
                        "total_cents": total_charge,
                        "paid_until_iso": paid_until.isoformat(),
                        "payment_provider": normalized_provider,
                        "payment_reference": normalized_event_id,
                    }
                ],
                due_at=issued_at,
                status="paid",
                payment_method=normalized_provider,
                issued_at=issued_at,
            )
        return {"status": "processed", "event_id": event.event_id}

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
            paid_until = self._subscription_due_date(
                tenant.tenant_id,
                subscription,
                self._current_period()[2].date(),
            )
            return BillingUpgradeCompleteResponse(
                status="already_active",
                prorated_charge_cents=0,
                prorated_charge=0,
                old_remaining_credit_cents=0,
                next_period_charge_cents=0,
                total_charge_cents=0,
                paid_until_iso=paid_until.isoformat(),
            )
        preview = self._compute_upgrade_proration(subscription, normalized_plan, normalized_period)
        if preview is None:
            raise ValueError("Érvénytelen csomagváltás.")
        old_remaining_credit = int(preview["old_remaining_credit_cents"])
        next_period_charge = int(preview["next_period_charge_cents"])
        total_charge = int(preview["total_charge_cents"])
        paid_until = date.fromisoformat(str(preview["paid_until_iso"]))
        verified_invoice = self._latest_verified_upgrade_invoice(
            tenant_id=tenant.tenant_id,
            target_plan=normalized_plan,
            target_period=normalized_period,
        )
        return BillingUpgradeCompleteResponse(
            status="paid_pending_activation" if verified_invoice is not None else "pending_payment",
            prorated_charge_cents=0,
            prorated_charge=0,
            old_remaining_credit_cents=old_remaining_credit,
            next_period_charge_cents=next_period_charge,
            total_charge_cents=total_charge,
            paid_until_iso=paid_until.isoformat(),
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
        if self._is_scheduled_change(subscription, normalized_plan, normalized_period):
            updated = self._upsert_subscription_from_existing(
                tenant.tenant_id,
                subscription,
                scheduled_plan_code=normalized_plan,
                scheduled_billing_period=normalized_period,
                scheduled_change_effective_period=effective_period_key,
            )
            self._sync_tenant_config(tenant, updated)
            return {
                "status": "scheduled",
                "message": "A visszalépés a kifizetett számlázási időszak után lép életbe. A már kifizetett időszak díját nem térítjük vissza.",
            }
        was_free_checkout = subscription.plan_code == "free" and normalized_plan != "free"
        if was_free_checkout:
            plan = plans[normalized_plan]
            period_multiplier = self._billing_period_multiplier(normalized_period)
            unit_price_cents = self._plan_monthly_charge_after_discount(plan.price_cents, normalized_period)
            total_cents = unit_price_cents * period_multiplier
            return {
                "status": "checkout_required",
                "message": "A fizetős előfizetés csak verified payment webhook után aktiválódik.",
                "provider": self._billing_provider(),
                "amount_cents": total_cents,
                "currency": self.default_currency,
                "checkout_metadata": {
                    "tenant_id": int(getattr(tenant, "tenant_id", 0) or 0),
                    "tenant_slug": str(getattr(tenant, "slug", "") or ""),
                    "flow": "plan_upgrade",
                    "target_plan": str(normalized_plan),
                    "billing_period": str(normalized_period),
                    "amount_cents": str(total_cents),
                },
            }
        paid_until = self._paid_until_after_upgrade(self.clock.now().date(), normalized_period) if was_free_checkout else None
        self._apply_immediate_plan_change(
            tenant,
            subscription,
            normalized_plan,
            normalized_period,
            paid_until=datetime.combine(paid_until, datetime.min.time(), tzinfo=UTC) if paid_until is not None else None,
        )
        if was_free_checkout:
            issued_at = self.clock.now()
            plan = plans[normalized_plan]
            period_multiplier = self._billing_period_multiplier(normalized_period)
            unit_price_cents = self._plan_monthly_charge_after_discount(plan.price_cents, normalized_period)
            total_cents = unit_price_cents * period_multiplier
            period_key = f"{issued_at:%Y%m%d%H%M%S%f}"[:16]
            if self._repo.get_invoice(tenant.tenant_id, "monthly_subscription", period_key) is None:
                self._repo.create_invoice(
                    tenant.tenant_id,
                    invoice_type="monthly_subscription",
                    period_key=period_key,
                    currency=self.default_currency,
                    total_cents=total_cents,
                    description=f"{plan.name} {self._billing_period_label(normalized_period)} díj",
                    lines=[
                        {
                            "code": plan.code,
                            "name": plan.name,
                            "billing_period": normalized_period,
                            "period_multiplier": period_multiplier,
                            "unit_price_cents": unit_price_cents,
                            "quantity": 1,
                            "total_cents": total_cents,
                            "paid_until_iso": paid_until.isoformat() if paid_until is not None else None,
                            "simulated_payment": self._is_simulated_provider(),
                            "payment_provider": self._billing_provider(),
                            "payment_reference": None,
                        }
                    ],
                    due_at=issued_at,
                    status=self._invoice_paid_status(),
                    payment_method=self._invoice_payment_method(),
                    issued_at=issued_at,
                )
        return {"status": "updated", "message": "A csomag azonnal frissült."}

    def complete_subscription_billing(
        self,
        tenant,
        subscription: BillingSubscriptionORM | None = None,
        *,
        outcome: str,
        force: bool = False,
        force_new_invoice: bool = False,
    ) -> BillingDebugBillingRunResponse:
        subscription = subscription or self.ensure_subscription(tenant)
        _, _, period_end_dt, _ = self._current_period()
        billing_date = self._billing_due_date(subscription, period_end_dt.date())
        now = self.clock.now()
        if now.date() < billing_date and not force:
            return BillingDebugBillingRunResponse(
                status="not_due",
                message="Ma még nincs számlázási nap.",
                billing_date=billing_date.isoformat(),
            )
        current_period_key, _, _, _ = self._current_period()
        if subscription.scheduled_plan_code and subscription.scheduled_change_effective_period == current_period_key:
            subscription = self._upsert_subscription_from_existing(
                tenant.tenant_id,
                subscription,
                plan_code=subscription.scheduled_plan_code,
                billing_period=subscription.scheduled_billing_period or subscription.billing_period,
                status=SubscriptionStatus.ACTIVE.value
                if subscription.scheduled_plan_code != "free"
                else SubscriptionStatus.TRIAL.value,
                trial_started_at=subscription.trial_started_at if subscription.scheduled_plan_code == "free" else None,
                trial_ends_at=subscription.trial_ends_at if subscription.scheduled_plan_code == "free" else None,
                scheduled_plan_code=None,
                scheduled_billing_period=None,
                scheduled_change_effective_period=None,
                question_warning_period_key=None,
                question_warning_level=0,
            )
        period_key = self._subscription_period_key(billing_date)
        if force_new_invoice:
            period_key = f"{now:%Y%m%d%H%M%S%f}"[:16]
        plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
        resources = self._load_resource_counts()
        estimated = self._estimate_next_invoice(subscription, resources)
        total_cents = int(estimated["total_cents"] or 0)
        next_extra_storage_gb = int(estimated.get("next_extra_storage_gb") or 0)
        if outcome == "success":
            failed_to_settle = None if force_new_invoice else self._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription_failed")
            if failed_to_settle is not None and failed_to_settle.status == "payment_failed":
                paid = self._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription")
                paid_after_failed = False
                if paid is not None and paid.issued_at is not None and failed_to_settle.issued_at is not None:
                    try:
                        paid_after_failed = paid.issued_at > failed_to_settle.issued_at
                    except TypeError:
                        paid_after_failed = paid.issued_at.replace(tzinfo=None) > failed_to_settle.issued_at.replace(tzinfo=None)
                if not paid_after_failed:
                    period_key = str(failed_to_settle.period_key or period_key)
            existing = None if force_new_invoice else self._repo.get_invoice(tenant.tenant_id, "monthly_subscription", period_key)
            next_billing_date = self._next_billing_date_after(billing_date, subscription.billing_period)
            if existing is None:
                self._repo.create_invoice(
                    tenant.tenant_id,
                    invoice_type="monthly_subscription",
                    period_key=period_key,
                    currency=self.default_currency,
                    total_cents=total_cents,
                    description=f"{plan.name} {self._billing_period_label(subscription.billing_period)} díj",
                    lines=[
                        {
                            "code": plan.code,
                            "name": plan.name,
                            "billing_period": subscription.billing_period,
                            "period_multiplier": self._billing_period_multiplier(subscription.billing_period),
                            "unit_price_cents": self._plan_monthly_charge_after_discount(
                                plan.price_cents, subscription.billing_period
                            ),
                            "extra_kb_count": int(subscription.extra_kb_count or 0),
                            "extra_storage_gb": next_extra_storage_gb,
                            "total_cents": total_cents,
                            "next_billing_date": next_billing_date.isoformat(),
                        }
                    ],
                    due_at=now,
                    status=self._invoice_paid_status(),
                    payment_method=self._invoice_payment_method(),
                    issued_at=now,
                )
            self._upsert_subscription_from_existing(
                tenant.tenant_id,
                subscription,
                plan_code=subscription.scheduled_plan_code or subscription.plan_code,
                billing_period=subscription.scheduled_billing_period or subscription.billing_period,
                status=SubscriptionStatus.ACTIVE.value,
                trial_started_at=None,
                trial_ends_at=datetime.combine(next_billing_date, datetime.min.time(), tzinfo=UTC),
                extra_storage_gb=next_extra_storage_gb,
                scheduled_plan_code=None,
                scheduled_billing_period=None,
                scheduled_change_effective_period=None,
                question_warning_period_key=None,
                question_warning_level=0,
            )
            return BillingDebugBillingRunResponse(
                status="paid",
                message="Sikeres számlázás.",
                billing_date=billing_date.isoformat(),
                next_billing_date=next_billing_date.isoformat(),
            )
        if outcome == "failed":
            failed_period_key = period_key
            existing_failed = None if force_new_invoice else self._repo.get_invoice(tenant.tenant_id, "monthly_subscription_failed", failed_period_key)
            previous_failed = self._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription_failed")
            previous_grace_until = None
            if previous_failed is not None and previous_failed.status == "payment_failed":
                paid = self._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription")
                paid_after_failed = False
                if paid is not None and paid.issued_at is not None and previous_failed.issued_at is not None:
                    try:
                        paid_after_failed = paid.issued_at > previous_failed.issued_at
                    except TypeError:
                        paid_after_failed = paid.issued_at.replace(tzinfo=None) > previous_failed.issued_at.replace(tzinfo=None)
                if not paid_after_failed:
                    previous_grace_until = self._date_from_invoice_value(previous_failed.due_at)
            grace_until = previous_grace_until or (billing_date + timedelta(days=5))
            if existing_failed is None:
                self._repo.create_invoice(
                    tenant.tenant_id,
                    invoice_type="monthly_subscription_failed",
                    period_key=failed_period_key,
                    currency=self.default_currency,
                    total_cents=total_cents,
                    description=f"Sikertelen fizetés: {plan.name}",
                    lines=[
                        {
                            "code": plan.code,
                            "name": plan.name,
                            "billing_period": subscription.billing_period,
                            "extra_storage_gb": next_extra_storage_gb,
                            "total_cents": total_cents,
                            "payment_failed": True,
                        }
                    ],
                    due_at=datetime.combine(grace_until, datetime.min.time(), tzinfo=UTC),
                    status="payment_failed",
                    issued_at=now,
                )
            return BillingDebugBillingRunResponse(
                status="payment_failed",
                message="Sikertelen fizetés rögzítve.",
                billing_date=billing_date.isoformat(),
                grace_until=grace_until.isoformat(),
            )
        raise ValueError("Ismeretlen számlázási kimenet.")

    def settle_subscription(self, tenant) -> BillingDebugBillingRunResponse:
        subscription = self.ensure_subscription(tenant)
        resources = self._load_resource_counts()
        estimated = self._estimate_next_invoice(subscription, resources)
        total_cents = int(estimated.get("total_cents") or 0)
        payment = self._execute_payment(
            amount_cents=total_cents,
            description=f"Havi előfizetés rendezése: {subscription.plan_code}",
            metadata={
                "tenant_slug": str(getattr(tenant, "slug", "") or ""),
                "flow": "subscription_settle",
                "plan": str(subscription.plan_code),
                "billing_period": str(subscription.billing_period),
            },
        )
        if payment.success:
            settled = self.complete_subscription_billing(tenant, subscription=subscription, outcome="success", force=True)
            if payment.external_id:
                settled.message = f"{settled.message} Tranzakció: {payment.external_id}"
            return settled
        return self.complete_subscription_billing(tenant, subscription=subscription, outcome="failed", force=True)

    def purchase_addon(self, tenant, *, addon_code: str, quantity: int) -> BillingInvoiceResponse:
        addons = self._addon_map()
        normalized_code = (addon_code or "").strip().lower()
        if normalized_code not in addons:
            raise ValueError("Ismeretlen addon.")
        qty = max(1, int(quantity or 1))
        addon = addons[normalized_code]
        total_cents = addon.price_cents * qty
        payment = self._execute_payment(
            amount_cents=total_cents,
            description=f"Addon vásárlás: {addon.name} x {qty}",
            metadata={
                "tenant_slug": str(getattr(tenant, "slug", "") or ""),
                "flow": "addon_purchase",
                "addon_code": str(normalized_code),
                "quantity": str(qty),
            },
        )
        if not payment.success:
            raise ValueError(payment.message or "A fizetés nem sikerült.")
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
            plan = self._plan_map().get(subscription.plan_code) or self._plan_map()["free"]
            carryover_training_chars = max(
                int(carryover_training_chars or 0),
                int(plan.included_training_chars or 0),
            )
            carryover_training_chars += 500000 * qty
        updated = self._upsert_subscription_from_existing(
            tenant.tenant_id,
            subscription,
            extra_kb_count=extra_kb_count,
            extra_storage_gb=extra_storage_gb,
            carryover_addon_questions=carryover_addon_questions,
            carryover_training_chars=carryover_training_chars,
        )
        self._sync_tenant_config(tenant, updated)
        issued_at = self.clock.now()
        invoice = self._repo.create_invoice(
            tenant.tenant_id,
            invoice_type=f"addon:{normalized_code}",
            period_key=f"{issued_at:%Y%m%d%H%M%S%f}"[:16],
            currency=DEFAULT_CURRENCY,
            total_cents=total_cents,
            description=f"{addon.name} x {qty}",
            lines=[
                {
                    "code": addon.code,
                    "name": addon.name,
                    "quantity": qty,
                    "unit_price_cents": addon.price_cents,
                    "total_cents": total_cents,
                    "simulated_payment": self._is_simulated_provider(),
                    "payment_provider": self._billing_provider(),
                    "payment_reference": payment.external_id,
                }
            ],
            due_at=issued_at,
            status=self._invoice_paid_status(),
            payment_method=self._invoice_payment_method(),
            issued_at=issued_at,
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
        self._upsert_subscription_from_existing(
            tenant.tenant_id,
            subscription,
            question_warning_period_key=period_key,
            question_warning_level=target_level,
        )

    def process_due_cycles(self) -> None:
        if isinstance(self.clock, BillingDebugClock) and self.clock.simulated_date is not None:
            return
        self._cycle_processor.process()


__all__ = [
    "BillingAddonPurchaseRequest",
    "BillingCatalogEntryORM",
    "BillingInvoiceORM",
    "BillingQuestionUsageORM",
    "BillingRepository",
    "BillingService",
    "BillingSubscriptionORM",
    "BillingTrainingUsageORM",
]
