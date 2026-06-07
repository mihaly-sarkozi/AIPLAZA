# backend/apps/traffic/repositories/TrafficQuestionUsageRepository.py
# Feladat: A TrafficQuestionUsageRepository DB-atomikus kérdésfoglalást végez. Egy tranzakcióban ellenőrzi a keretet, növeli az aggregált számlálókat és append-only eventet ír.

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy import text

from apps.traffic.schemas.TrafficQuestionReservationResult import TrafficQuestionReservationResult


QUESTION_LIMIT_EXCEEDED_MESSAGE = "Elfogyott a kérdésszám kereted. Vásárolj addon kérdéscsomagot."


class TrafficQuestionUsageRepository:
    """Kérdéshasználat írása és quota foglalása public traffic táblákban."""

    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]) -> None:
        self._session_factory = session_factory

    def reserve_question(
        self,
        *,
        tenant_id: int,
        user_id: int,
        period_key: str,
        request_context: dict[str, Any] | None = None,
    ) -> TrafficQuestionReservationResult:
        """Atomikusan lefoglal egy kérdést, ha a tenant időszaki kerete még nem fogyott el."""

        context_json = json.dumps(request_context or {}, ensure_ascii=False)
        with self._session_factory() as db:
            try:
                db.execute(text("SET search_path TO public"))
                available_total = self._load_available_questions_total(db, tenant_id)
                db.execute(
                    text(
                        """
                        INSERT INTO public.traffic_question_usage_totals (tenant_id, period_key, question_count)
                        VALUES (:tenant_id, :period_key, 0)
                        ON CONFLICT (tenant_id, period_key) DO NOTHING
                        """
                    ),
                    {"tenant_id": tenant_id, "period_key": period_key},
                )
                total_row = db.execute(
                    text(
                        """
                        SELECT question_count
                        FROM public.traffic_question_usage_totals
                        WHERE tenant_id = :tenant_id AND period_key = :period_key
                        FOR UPDATE
                        """
                    ),
                    {"tenant_id": tenant_id, "period_key": period_key},
                ).mappings().one()
                used_total = int(total_row["question_count"] or 0)
                if available_total <= 0 or used_total >= available_total:
                    db.rollback()
                    return TrafficQuestionReservationResult(
                        allowed=False,
                        reason=QUESTION_LIMIT_EXCEEDED_MESSAGE,
                        period_key=period_key,
                        used_total=used_total,
                        available_total=max(0, available_total),
                        remaining_total=0,
                    )

                db.execute(
                    text(
                        """
                        INSERT INTO public.traffic_question_usage (tenant_id, user_id, period_key, question_count, last_question_at)
                        VALUES (:tenant_id, :user_id, :period_key, 1, NOW())
                        ON CONFLICT (tenant_id, user_id, period_key)
                        DO UPDATE SET
                            question_count = public.traffic_question_usage.question_count + 1,
                            last_question_at = NOW(),
                            updated_at = NOW()
                        """
                    ),
                    {"tenant_id": tenant_id, "user_id": user_id, "period_key": period_key},
                )
                db.execute(
                    text(
                        """
                        UPDATE public.traffic_question_usage_totals
                        SET question_count = question_count + 1,
                            last_question_at = NOW(),
                            updated_at = NOW()
                        WHERE tenant_id = :tenant_id AND period_key = :period_key
                        """
                    ),
                    {"tenant_id": tenant_id, "period_key": period_key},
                )
                db.execute(
                    text(
                        """
                        INSERT INTO public.traffic_question_events (
                            tenant_id, user_id, period_key, event_type, question_delta, request_context
                        )
                        VALUES (
                            :tenant_id, :user_id, :period_key, 'reserved', 1, CAST(:request_context AS jsonb)
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "period_key": period_key,
                        "request_context": context_json,
                    },
                )
                db.commit()
                new_total = used_total + 1
                return TrafficQuestionReservationResult(
                    allowed=True,
                    reason=None,
                    period_key=period_key,
                    used_total=new_total,
                    available_total=available_total,
                    remaining_total=max(0, available_total - new_total),
                )
            except Exception:
                db.rollback()
                raise

    def _load_available_questions_total(self, db: Any, tenant_id: int) -> int:
        """Public billing subscription/catalog adatokból kiszámolja az aktuális kérdéskeretet."""

        subscription = db.execute(
            text(
                """
                SELECT plan_code, carryover_addon_questions
                FROM public.billing_subscriptions
                WHERE tenant_id = :tenant_id
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        ).mappings().first()
        plan_code = str((subscription or {}).get("plan_code") or "free")
        carryover = int((subscription or {}).get("carryover_addon_questions") or 0)
        plan = db.execute(
            text(
                """
                SELECT included
                FROM public.billing_catalog_entries
                WHERE entry_type = 'plan' AND code = :plan_code AND is_active IS TRUE
                LIMIT 1
                """
            ),
            {"plan_code": plan_code},
        ).mappings().first()
        if plan is None and plan_code != "free":
            plan = db.execute(
                text(
                    """
                    SELECT included
                    FROM public.billing_catalog_entries
                    WHERE entry_type = 'plan' AND code = 'free' AND is_active IS TRUE
                    LIMIT 1
                    """
                )
            ).mappings().first()
        included = dict((plan or {}).get("included") or {})
        monthly_included = int(included.get("questions_monthly") or 0)
        return max(0, monthly_included + max(0, carryover))


__all__ = ["QUESTION_LIMIT_EXCEEDED_MESSAGE", "TrafficQuestionUsageRepository"]
