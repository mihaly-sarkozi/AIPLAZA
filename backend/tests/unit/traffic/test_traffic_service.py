# backend/tests/unit/traffic/test_traffic_service.py
# Feladat: A TrafficService read modell és DB-atomikus kérdésfoglalás integrációs pontjainak unit tesztjei.

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apps.traffic.schemas.TrafficQuestionReservationResult import TrafficQuestionReservationResult
from apps.traffic.service.TrafficService import TrafficService


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 6, 6, tzinfo=UTC)


class FakeTrafficRepository:
    def list_catalog(self):
        return [
            {
                "entry_type": "plan",
                "code": "free",
                "name": "Free",
                "currency": "EUR",
                "price_cents": 0,
                "included": {
                    "knowledge_bases": 1,
                    "storage_gb": 1,
                    "questions_monthly": 3,
                    "training_chars": 1000,
                    "max_users": 5,
                    "trial_days": 7,
                },
                "metadata": {},
            }
        ]

    def get_subscription(self, tenant_id: int):
        return {
            "plan_code": "free",
            "billing_period": "monthly",
            "status": "trial",
            "extra_kb_count": 0,
            "extra_storage_gb": 0,
            "carryover_addon_questions": 2,
            "carryover_training_chars": 1000,
        }

    def list_question_usage(self, tenant_id: int, period_key: str):
        return [{"user_id": 12, "question_count": 2}]

    def get_training_usage(self, tenant_id: int, period_key: str):
        return {"trained_chars": 100, "storage_bytes": 0}

    def load_user_map(self):
        return {12: SimpleNamespace(name="Admin", email="admin@example.test")}

    def load_resource_counts(self):
        return {"users": 1, "knowledge_bases": 1, "storage_bytes": 0}

    def list_training_addon_invoice_lines(self, tenant_id: int):
        return []


class FakeQuestionUsageRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def reserve_question(self, **kwargs):
        self.calls.append(kwargs)
        return TrafficQuestionReservationResult(
            allowed=True,
            reason=None,
            period_key=kwargs["period_key"],
            used_total=1,
            available_total=5,
            remaining_total=4,
        )


def test_reserve_question_delegates_to_atomic_repository():
    question_repo = FakeQuestionUsageRepository()
    service = TrafficService(FakeTrafficRepository(), question_usage_repository=question_repo, clock=FixedClock())

    result = service.reserve_question(
        SimpleNamespace(tenant_id=7),
        12,
        request_context={"source": "test"},
    )

    assert result.allowed is True
    assert question_repo.calls == [
        {
            "tenant_id": 7,
            "user_id": 12,
            "period_key": "2026-06",
            "request_context": {"source": "test"},
        }
    ]


def test_overview_uses_traffic_usage_rows():
    service = TrafficService(
        FakeTrafficRepository(),
        question_usage_repository=FakeQuestionUsageRepository(),
        clock=FixedClock(),
    )

    overview = service.get_overview(SimpleNamespace(tenant_id=7))

    assert overview.usage["questions"]["used_total"] == 2
    assert overview.usage["questions"]["available_total"] == 5
    assert overview.usage["questions_by_user"][0]["email"] == "admin@example.test"
