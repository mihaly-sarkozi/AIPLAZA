from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.retrieval_profile import RetrievalProfile
from core.kernel.interface.observability import (
    increment_metric as increment_platform_metric,
    log_structured_event,
    observe_metric as observe_platform_metric,
)

logger = logging.getLogger(__name__)


class RetrievalResilienceRunner:
    def __init__(
        self,
        *,
        retrieval_engine: Any,
        metrics_store: Any,
        timeout_seconds: float = 3.0,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 0.05,
    ) -> None:
        self._retrieval_engine = retrieval_engine
        self._metrics_store = metrics_store
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    async def retrieve_hits(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        builds: list[IndexBuild],
        retrieval_profile: RetrievalProfile,
        query_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        last_error: BaseException | None = None
        for attempt in range(1, self._retry_attempts + 1):
            started = time.perf_counter()
            try:
                hits = await asyncio.wait_for(
                    self._retrieval_engine.retrieve(
                        query=query,
                        builds=builds,
                        retrieval_profile=retrieval_profile,
                        query_profile=query_profile,
                    ),
                    timeout=self._timeout_seconds,
                )
                duration_ms = (time.perf_counter() - started) * 1000.0
                self._metrics_store.record_timing("query_retrieval_duration_ms", duration_ms)
                observe_platform_metric("knowledge.query.retrieval.duration_ms", duration_ms, unit="ms")
                return hits
            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                self._record_retry("timeout", tenant, corpus_uuid, attempt, exc)
            except (RuntimeError, ValueError, ConnectionError, OSError) as exc:
                last_error = exc
                self._record_retry("error", tenant, corpus_uuid, attempt, exc)
            if attempt < self._retry_attempts:
                await asyncio.sleep(self._retry_backoff_seconds * attempt)
        self._record_fallback(tenant, corpus_uuid, last_error)
        return []

    def _record_retry(self, kind: str, tenant: str, corpus_uuid: str, attempt: int, exc: BaseException) -> None:
        metric_suffix = "timeout" if kind == "timeout" else "error"
        self._metrics_store.increment(f"query_retrieval_{metric_suffix}_count", 1)
        increment_platform_metric(f"knowledge.query.retrieval.{metric_suffix}.count", 1.0)
        log_structured_event(
            "apps.knowledge",
            f"knowledge.query.retrieval_{metric_suffix}",
            level=logging.WARNING,
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            retry_count=attempt,
            timeout_sec=self._timeout_seconds if kind == "timeout" else None,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    def _record_fallback(self, tenant: str, corpus_uuid: str, last_error: BaseException | None) -> None:
        self._metrics_store.increment("query_retrieval_fallback_count", 1)
        increment_platform_metric("knowledge.query.retrieval.fallback.count", 1.0)
        if last_error is not None:
            log_structured_event(
                "apps.knowledge",
                "knowledge.query.retrieval_profile_fallback",
                level=logging.WARNING,
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                error_type=type(last_error).__name__,
                error_message=str(last_error),
            )


__all__ = ["RetrievalResilienceRunner"]
