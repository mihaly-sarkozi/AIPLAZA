from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from apps.chat.channel_quota import release_usage_slot, reserve_usage_slot
from apps.chat.service.llm_budget import LlmBudgetConfig, LlmBudgetManager
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE
from apps.knowledge.service.retrieval_resilience_runner import RetrievalResilienceRunner

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_llm_budget_memory_fallback_enforces_concurrency_under_parallel_load() -> None:
    manager = LlmBudgetManager(
        config=LlmBudgetConfig(
            request_limit_per_minute=100,
            prompt_chars_per_minute=100_000,
            concurrency_limit=3,
            tenant_daily_tokens=100_000,
            tenant_monthly_tokens=1_000_000,
            estimated_completion_tokens=10,
            input_cost_per_1k_tokens_usd=0.001,
            output_cost_per_1k_tokens_usd=0.001,
            global_daily_spend_usd=100.0,
            chat_max_tokens=100,
        ),
        redis_getter=lambda: None,
    )
    barrier = threading.Barrier(12)
    reservations: list[dict | None] = []
    lock = threading.Lock()

    def _attempt() -> bool:
        barrier.wait()
        allowed, _, reservation = manager.acquire(tenant_id=1, scope="chat", prompt_chars=100)
        with lock:
            reservations.append(reservation)
        return allowed

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: _attempt(), range(12)))

    assert sum(1 for item in results if item) == 3
    assert sum(1 for item in results if not item) == 9
    for reservation in reservations:
        manager.release(reservation)
    assert manager._state[("1", "chat")]["inflight"] == 0


def test_channel_quota_memory_fallback_enforces_per_minute_under_parallel_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.chat.channel_quota.get_rate_limit_redis", lambda: None)
    quota_lock = threading.RLock()
    counters: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    barrier = threading.Barrier(10)
    reservations: list[dict | None] = []
    reservation_lock = threading.Lock()

    def _attempt() -> bool:
        barrier.wait()
        allowed, _, reservation = reserve_usage_slot(
            tenant_id=1,
            credential_id=99,
            daily_limit=100,
            per_minute_limit=4,
            now=now,
            period_key="2026-05-23",
            quota_lock=quota_lock,
            quota_fallback_counters=counters,
        )
        with reservation_lock:
            reservations.append(reservation)
        return allowed

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: _attempt(), range(10)))

    assert sum(1 for item in results if item) == 4
    assert sum(1 for item in results if not item) == 6
    for reservation in reservations:
        release_usage_slot(reservation, quota_lock=quota_lock, quota_fallback_counters=counters)
    assert counters == {}


@pytest.mark.asyncio
async def test_retrieval_resilience_timeout_fallback_records_single_failure_class() -> None:
    class SlowRetrievalEngine:
        async def retrieve(self, **_kwargs):
            await asyncio.sleep(0.05)
            return [{"id": "late"}]

    class MetricsStore:
        def __init__(self) -> None:
            self.increments: list[tuple[str, int]] = []
            self.timings: list[tuple[str, float]] = []

        def increment(self, key: str, value: int) -> None:
            self.increments.append((key, value))

        def record_timing(self, key: str, value: float) -> None:
            self.timings.append((key, value))

    metrics = MetricsStore()
    runner = RetrievalResilienceRunner(
        retrieval_engine=SlowRetrievalEngine(),
        metrics_store=metrics,
        timeout_seconds=0.001,
        retry_attempts=2,
        retry_backoff_seconds=0.001,
    )

    hits = await runner.retrieve_hits(
        tenant="demo",
        corpus_uuid="kb-1",
        query="slow query",
        builds=[SimpleNamespace(id="build-1")],
        retrieval_profile=DEFAULT_RETRIEVAL_PROFILE,
        query_profile={},
    )

    assert hits == []
    assert metrics.increments.count(("query_retrieval_timeout_count", 1)) == 2
    assert ("query_retrieval_fallback_count", 1) in metrics.increments
    assert metrics.timings == []
