from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.index_profile import DEFAULT_INDEX_PROFILE
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.service.facade_helpers import utcnow as utcnow

logger = logging.getLogger(__name__)


class IngestAutoIndexService:
    def __init__(
        self,
        *,
        ingest_run_store: Any,
        load_existing_semantic_blocks: Callable[..., list[dict[str, Any]]],
        schedule_index_build: Callable[..., Any],
        run_index_build: Callable[[str], Any],
    ) -> None:
        self._ingest_run_store = ingest_run_store
        self._load_existing_semantic_blocks = load_existing_semantic_blocks
        self._schedule_index_build = schedule_index_build
        self._run_index_build = run_index_build

    @staticmethod
    def _store(value: Any) -> Any:
        return value() if callable(value) else value

    def refresh_after_ingest(self, run: IngestRun) -> None:
        if not self._should_schedule(run):
            return
        try:
            build = self._schedule_index_build(
                tenant=run.tenant,
                corpus_uuid=run.corpus_uuid,
                index_profile_key=DEFAULT_INDEX_PROFILE.key,
                created_by=run.created_by,
            )
            self._update_run_metadata(
                run.id,
                {
                    "semantic_block_auto_index_status": "scheduled",
                    "index_progress_state": "embedding_queued",
                    "semantic_block_auto_index_build_id": build.id,
                },
            )

            async def _run() -> None:
                try:
                    self._update_run_metadata(run.id, {"index_progress_state": "embedding_started"})
                    finished = await self._run_index_build(build.id)
                    self._update_run_metadata(
                        run.id,
                        {
                            "semantic_block_auto_index_status": finished.status,
                            "semantic_block_auto_index_build_id": finished.id,
                            "index_progress_state": "index_ready" if finished.status == "ready" else "index_failed",
                        },
                    )
                except Exception as exc:
                    logger.warning("semantic block auto index task failed: %s", exc, exc_info=True)
                    self._mark_failed(run.id, exc)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_run())
            else:
                loop.create_task(_run())
        except Exception as exc:
            logger.warning("semantic block auto index refresh failed: %s", exc, exc_info=True)
            self._mark_failed(run.id, exc)

    def _should_schedule(self, run: IngestRun) -> bool:
        if run.status not in {"completed", "partial_success"}:
            return False
        semantic_blocks = self._load_existing_semantic_blocks(
            corpus_uuid=run.corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        if not semantic_blocks:
            return False
        return dict(run.metadata or {}).get("semantic_block_auto_index_status") not in {"completed", "scheduled"}

    def _update_run_metadata(self, run_id: str, updates: dict[str, Any]) -> None:
        ingest_run_store = self._store(self._ingest_run_store)
        latest = ingest_run_store.get(run_id)
        if latest is None:
            return
        ingest_run_store.update(
            replace(
                latest,
                metadata={**dict(latest.metadata or {}), **updates},
                updated_at=utcnow(),
            )
        )

    def _mark_failed(self, run_id: str, exc: Exception) -> None:
        self._update_run_metadata(
            run_id,
            {
                "semantic_block_auto_index_status": "failed",
                "semantic_block_auto_index_error": str(exc),
                "index_progress_state": "index_failed",
            },
        )


__all__ = ["IngestAutoIndexService"]
