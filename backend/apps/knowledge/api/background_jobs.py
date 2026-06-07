# backend/apps/knowledge/api/background_jobs.py
# Feladat: Knowledge ingest és index háttérfeladatok routertől leválasztott segédlogikája. Outbox enqueue-t, index build retry/concurrency limitet és workerből futtatott stale run recovery sweepet kezel, request apphoz kötött BackgroundTasks fallback nélkül. Program-specifikus knowledge API background job support.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from apps.knowledge.ingest_jobs import process_ingest_run_and_start_index_async
from core.kernel.config.config_loader import settings
from core.kernel.jobs import enqueue_job
from core.modules.tenant.context.tenant_context import run_async_with_tenant_schema

logger = logging.getLogger(__name__)

INDEX_WORKER_CONCURRENCY = max(1, int(getattr(settings, "embedding_worker_concurrency", 2) or 2))
INDEX_WORKER_SEMAPHORE = threading.Semaphore(INDEX_WORKER_CONCURRENCY)


async def process_ingest_run_and_start_index(
    tenant_slug: str | None,
    facade: Any,
    run_id: str,
    created_by: int | None,
    tenant_for_usage: Any | None = None,
) -> None:
    await process_ingest_run_and_start_index_async(
        tenant_slug=tenant_slug,
        run_id=run_id,
        created_by=created_by,
        facade=facade,
    )


def enqueue_ingest_pipeline_job(
    *,
    tenant_slug: str | None,
    run_id: str,
    created_by: int | None,
    facade: Any,
) -> None:
    enqueue_job(
        "knowledge.ingest_pipeline",
        {
            "tenant_slug": tenant_slug,
            "run_id": run_id,
            "created_by": created_by,
        },
        idempotency_key=f"knowledge.ingest_pipeline:{tenant_slug or '_'}:{run_id}",
    )


def enqueue_index_build_job(
    *,
    tenant_slug: str | None,
    build_id: str,
) -> None:
    enqueue_job(
        "knowledge.index_build",
        {
            "tenant_slug": tenant_slug,
            "build_id": build_id,
        },
        idempotency_key=f"knowledge.index_build:{tenant_slug or '_'}:{build_id}",
    )


def enqueue_ingest_item_reprocess_job(
    *,
    tenant_slug: str | None,
    item_id: str,
    current_user_id: int | None,
) -> None:
    enqueue_job(
        "knowledge.ingest_item_reprocess",
        {
            "tenant_slug": tenant_slug,
            "item_id": item_id,
            "current_user_id": current_user_id,
        },
        idempotency_key=f"knowledge.ingest_item_reprocess:{tenant_slug or '_'}:{item_id}",
    )


def enqueue_recovery_sweep_job(*, tenant_slug: str | None) -> None:
    enqueue_job(
        "knowledge.recovery_sweep",
        {
            "tenant_slug": tenant_slug,
        },
        idempotency_key=f"knowledge.recovery_sweep:{tenant_slug or '_'}",
    )


async def run_index_build_with_retry(
    tenant_slug: str | None,
    facade: Any,
    build_id: str,
    *,
    retries: int = 1,
) -> None:
    attempts = max(1, int(retries) + 1)
    runner = getattr(facade, "run_index_build_with_retry", None)
    if not callable(runner):
        runner = getattr(facade, "run_index_build", None)
    if not callable(runner):
        raise AttributeError("Facade does not provide run_index_build_with_retry or run_index_build")
    for attempt in range(1, attempts + 1):
        try:
            await run_async_with_tenant_schema(tenant_slug, runner, build_id)
            return
        except (RuntimeError, ValueError, TimeoutError):
            if attempt >= attempts:
                logger.exception(
                    "Index build failed after retries",
                    extra={"build_id": build_id, "tenant_slug": tenant_slug, "attempts": attempts},
                )
                raise
            logger.warning(
                "Index build failed, retrying",
                extra={"build_id": build_id, "tenant_slug": tenant_slug, "attempt": attempt, "attempts": attempts},
            )


def run_index_build_worker_task(
    tenant_slug: str | None,
    facade: Any,
    build_id: str,
) -> None:
    acquired = INDEX_WORKER_SEMAPHORE.acquire(timeout=1)
    if not acquired:
        logger.warning(
            "Index worker semaphore acquire timeout",
            extra={"build_id": build_id, "tenant_slug": tenant_slug},
        )
        INDEX_WORKER_SEMAPHORE.acquire()
    try:
        asyncio.run(run_index_build_with_retry(tenant_slug, facade, build_id))
    finally:
        INDEX_WORKER_SEMAPHORE.release()


def run_recovery_sweep_for_tenant(tenant_slug: str | None, facade: Any, current_user_id: int | None = None) -> None:
    corpus_list = facade.list_all_unfiltered()
    for corpus in corpus_list:
        corpus_uuid = str(getattr(corpus, "uuid", "") or "")
        if not corpus_uuid:
            continue
        runs = facade.list_ingest_runs(corpus_uuid, limit=50, offset=0)
        for run in runs:
            if run.status not in {"queued", "processing"}:
                continue
            items = facade.list_ingest_items(run.id)
            stale_items = [item for item in items if facade.is_ingest_item_stale_processing(item)]
            if stale_items:
                for stale_item in stale_items:
                    try:
                        facade.request_ingest_item_reprocess(stale_item.id, current_user_id=current_user_id)
                        enqueue_ingest_item_reprocess_job(
                            tenant_slug=tenant_slug,
                            item_id=stale_item.id,
                            current_user_id=current_user_id,
                        )
                    except (RuntimeError, ValueError):
                        logger.exception(
                            "Knowledge stale ingest item recovery failed",
                            extra={"tenant_slug": tenant_slug, "run_id": run.id, "item_id": stale_item.id},
                        )
                continue
            if facade.is_ingest_run_stale(run):
                try:
                    facade.mark_ingest_run_failed_as_stale(
                        run.id,
                        reason="Ingest run stalled without progressing items.",
                    )
                except (RuntimeError, ValueError):
                    logger.exception(
                        "Knowledge stale ingest run fail-safe failed",
                        extra={"tenant_slug": tenant_slug, "run_id": run.id},
                    )
        for build in facade.list_index_builds(corpus_uuid):
            if not facade.is_index_build_stale(build):
                continue
            try:
                facade.mark_index_build_failed_as_stale(
                    build.id,
                    reason="Index build stalled and was marked failed by recovery sweep.",
                )
            except (RuntimeError, ValueError):
                logger.exception(
                    "Knowledge stale index build fail-safe failed",
                    extra={"tenant_slug": tenant_slug, "build_id": build.id},
                )

__all__ = [
    "enqueue_index_build_job",
    "enqueue_ingest_pipeline_job",
    "enqueue_ingest_item_reprocess_job",
    "enqueue_recovery_sweep_job",
    "process_ingest_run_and_start_index",
    "run_index_build_with_retry",
    "run_index_build_worker_task",
    "run_recovery_sweep_for_tenant",
]
