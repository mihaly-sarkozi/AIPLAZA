# backend/apps/traffic/service/TrafficService.py
# Feladat: A TrafficService application service osztályt tartalmazza. A repository nyers usage adataiból forgalmi read modellt aggregál a frontend számára.

from __future__ import annotations

from typing import Any

from apps.traffic.repositories.TrafficQuestionUsageRepository import TrafficQuestionUsageRepository
from apps.traffic.repositories.TrafficRepository import TrafficRepository
from apps.traffic.schemas.TrafficCatalogEntryResponse import TrafficCatalogEntryResponse
from apps.traffic.schemas.TrafficOverviewResponse import TrafficOverviewResponse
from apps.traffic.schemas.TrafficQuestionReservationResult import TrafficQuestionReservationResult
from apps.traffic.schemas.TrafficQuestionUserUsageResponse import TrafficQuestionUserUsageResponse
from shared.utils.clock import Clock, SystemClock
from shared.utils.datetime_utils import current_month_period
from shared.utils.number_utils import money_from_cents, non_negative_int, round_storage_gb, string_or_default


class TrafficService:
    """A forgalom oldal read-only üzleti logikája.

    Nem indít számlázást és nem módosít előfizetést. Csak összegyűjti és aggregálja
    a billing/knowledge/user táblákban tárolt használati adatokat.
    """

    def __init__(
        self,
        repository: TrafficRepository,
        question_usage_repository: TrafficQuestionUsageRepository,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._question_usage_repository = question_usage_repository
        self._clock = clock or SystemClock()

    def reserve_question(
        self,
        tenant: Any,
        user_id: int,
        request_context: dict[str, Any] | None = None,
    ) -> TrafficQuestionReservationResult:
        """DB-tranzakcióban lefoglal és rögzít egy kérdést, ha van még tenant kérdéskeret."""

        period_key, _, _, _ = current_month_period(self._clock.now())
        return self._question_usage_repository.reserve_question(
            tenant_id=int(tenant.tenant_id),
            user_id=int(user_id),
            period_key=period_key,
            request_context=request_context,
        )

    def get_overview(self, tenant: Any) -> TrafficOverviewResponse:
        """Összerakja az aktuális tenant forgalmi áttekintését a frontend oldalnak."""

        tenant_id = int(tenant.tenant_id)
        period_key, period_start_dt, period_end_dt, _ = current_month_period(self._clock.now())
        catalog_rows = self._repository.list_catalog()
        subscription = self._repository.get_subscription(tenant_id)
        plan_code = self._subscription_value(subscription, "plan_code", "free")
        billing_period = self._subscription_value(subscription, "billing_period", "monthly")
        status = self._subscription_value(subscription, "status", "trial")

        question_usage, questions_by_user = self._question_usage_summary(tenant_id, period_key, subscription, catalog_rows)
        training_usage = self._training_usage_summary(tenant_id, period_key, subscription, catalog_rows)
        resources = self._resource_summary()
        limits = self._build_limits(subscription, catalog_rows)

        return TrafficOverviewResponse(
            current_period_key=period_key,
            current_period_start_iso=period_start_dt.date().isoformat(),
            current_period_end_iso=period_end_dt.date().isoformat(),
            catalog=self._catalog_response(catalog_rows),
            subscription={
                "plan_code": plan_code,
                "billing_period": billing_period,
                "status": status,
                "extra_kb_count": self._subscription_int(subscription, "extra_kb_count"),
                "extra_storage_gb": self._subscription_int(subscription, "extra_storage_gb"),
                "carryover_addon_questions": self._subscription_int(subscription, "carryover_addon_questions"),
                "carryover_training_chars": self._subscription_int(subscription, "carryover_training_chars"),
            },
            limits=limits,
            usage={
                "resources": resources,
                "questions": question_usage,
                "training": training_usage,
                "questions_by_user": [item.model_dump() for item in questions_by_user],
            },
        )

    def _question_usage_summary(
        self,
        tenant_id: int,
        period_key: str,
        subscription: dict[str, Any] | None,
        catalog_rows: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[TrafficQuestionUserUsageResponse]]:
        """Kiszámolja az időszaki kérdéskeretet, felhasználást és felhasználónkénti bontást."""

        usage_rows = self._repository.list_question_usage(tenant_id, period_key)
        used_total = sum(int(row.get("question_count") or 0) for row in usage_rows)
        plan = self._current_plan(subscription, catalog_rows)
        monthly_included = int(plan.get("questions_monthly") or 0)
        addon_carryover = self._subscription_int(subscription, "carryover_addon_questions")
        available_total = monthly_included + addon_carryover
        consumed_from_addons = max(0, used_total - monthly_included)
        percent = int(round((used_total / available_total) * 100)) if available_total > 0 else 100
        user_map = self._repository.load_user_map()
        by_user = [
            TrafficQuestionUserUsageResponse(
                user_id=int(row.get("user_id") or 0),
                name=getattr(user_map.get(int(row.get("user_id") or 0)), "name", None),
                email=getattr(user_map.get(int(row.get("user_id") or 0)), "email", "") or "",
                question_count=int(row.get("question_count") or 0),
            )
            for row in usage_rows
        ]
        return (
            {
                "period_key": period_key,
                "used_total": used_total,
                "monthly_included": monthly_included,
                "remaining_included": max(0, monthly_included - used_total),
                "addon_carryover": addon_carryover,
                "remaining_addons": max(0, addon_carryover - consumed_from_addons),
                "remaining_total": max(0, available_total - used_total),
                "available_total": available_total,
                "percent_used": max(0, min(100, percent)),
            },
            by_user,
        )

    def _training_usage_summary(
        self,
        tenant_id: int,
        period_key: str,
        subscription: dict[str, Any] | None,
        catalog_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Kiszámolja a tanítási karakter- és tárhelyhasználatot az aktuális időszakra."""

        training = self._repository.get_training_usage(tenant_id, period_key)
        live_usage = self._repository.load_ingest_usage()
        trained_chars = max(int((training or {}).get("trained_chars") or 0), int(live_usage.get("trained_chars") or 0))
        storage_bytes = max(int((training or {}).get("storage_bytes") or 0), int(live_usage.get("storage_bytes") or 0))
        plan = self._current_plan(subscription, catalog_rows)
        included_chars = max(0, int(plan.get("training_chars") or 0))
        available_chars = self._available_training_chars(tenant_id, subscription, catalog_rows)
        return {
            "period_key": period_key,
            "trained_chars": trained_chars,
            "remaining_training_chars": max(0, available_chars - trained_chars),
            "available_training_chars": available_chars,
            "included_training_chars": included_chars,
            "addon_training_chars": max(0, available_chars - included_chars),
            "storage_bytes": storage_bytes,
            "storage_gb_used_rounded": round_storage_gb(storage_bytes),
        }

    def _resource_summary(self) -> dict[str, int]:
        """Tenant-sémás resource számlálókat egészíti ki a kerekített tárhely adattal."""

        resources = self._repository.load_resource_counts()
        storage_bytes = int(resources.get("storage_bytes") or 0)
        return {
            **resources,
            "storage_gb_used_rounded": round_storage_gb(storage_bytes),
        }

    def _build_limits(self, subscription: dict[str, Any] | None, catalog_rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Az aktuális csomag és recurring addonok alapján kiszámolja a forgalmi limiteket."""

        plan = self._current_plan(subscription, catalog_rows)
        return {
            "max_users": plan.get("max_users"),
            "knowledge_bases": int(plan.get("knowledge_bases") or 0) + self._subscription_int(subscription, "extra_kb_count"),
            "storage_gb": int(plan.get("storage_gb") or 0) + self._subscription_int(subscription, "extra_storage_gb"),
            "questions_monthly": int(plan.get("questions_monthly") or 0),
            "addon_questions_carryover": self._subscription_int(subscription, "carryover_addon_questions"),
            "training_chars_available": self._available_training_chars(0, subscription, catalog_rows),
            "trial_days": int(plan.get("trial_days") or 0),
        }

    def _available_training_chars(
        self,
        tenant_id: int,
        subscription: dict[str, Any] | None,
        catalog_rows: list[dict[str, Any]],
    ) -> int:
        """Meghatározza az elérhető tanítási karakterkeretet csomagból, carryoverből és fizetett addon számlákból."""

        plan = self._current_plan(subscription, catalog_rows)
        included = max(0, int(plan.get("training_chars") or 0))
        carryover = self._subscription_int(subscription, "carryover_training_chars")
        invoice_addon_chars = self._training_addon_invoice_chars(tenant_id, catalog_rows) if tenant_id else 0
        return max(included, carryover, included + invoice_addon_chars)

    def _training_addon_invoice_chars(self, tenant_id: int, catalog_rows: list[dict[str, Any]]) -> int:
        """A kifizetett tanítási addon invoice sorokból összesíti a plusz karakterkeretet."""

        addon_chars = {
            str(row.get("code") or ""): int((row.get("included") or {}).get("training_chars") or 1000000)
            for row in catalog_rows
            if row.get("entry_type") == "addon"
        }
        total = 0
        for line in self._repository.list_training_addon_invoice_lines(tenant_id):
            code = str(line.get("code") or "").strip()
            if code not in {"training_initial_500k", "training_extra_500k"}:
                continue
            quantity = max(1, int(line.get("quantity") or 1))
            total += max(0, addon_chars.get(code, 1000000)) * quantity
        return total

    def _current_plan(self, subscription: dict[str, Any] | None, catalog_rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Visszaadja az előfizetéshez tartozó plan objektumot, hiány esetén a free csomagot."""

        plans = {
            str(row.get("code") or ""): dict(row.get("included") or {})
            for row in catalog_rows
            if row.get("entry_type") == "plan"
        }
        plan_code = self._subscription_value(subscription, "plan_code", "free")
        return plans.get(plan_code) or plans["free"]

    def _catalog_response(self, catalog_rows: list[dict[str, Any]]) -> list[TrafficCatalogEntryResponse]:
        """Public catalog sorokat alakít traffic API response elemekké."""

        return [
            TrafficCatalogEntryResponse(
                entry_type=str(row.get("entry_type") or ""),
                code=str(row.get("code") or ""),
                name=str(row.get("name") or ""),
                currency=str(row.get("currency") or "EUR"),
                price_cents=int(row.get("price_cents") or 0),
                price=money_from_cents(int(row.get("price_cents") or 0)),
                included=dict(row.get("included") or {}),
                metadata=dict(row.get("metadata") or {}),
            )
            for row in catalog_rows
        ]

    @staticmethod
    def _subscription_value(subscription: dict[str, Any] | None, field_name: str, default: str) -> str:
        """Biztonságosan stringgé normalizál egy opcionális subscription mezőt."""

        value = subscription.get(field_name) if subscription is not None else None
        return string_or_default(value, default)

    @staticmethod
    def _subscription_int(subscription: dict[str, Any] | None, field_name: str) -> int:
        """Biztonságosan intté normalizál egy opcionális subscription számlálómezőt."""

        value = subscription.get(field_name, 0) if subscription is not None else 0
        return non_negative_int(value)


__all__ = ["TrafficService"]
