# backend/apps/knowledge/service/ingest_run_processor.py
# Owns ingest-run level orchestration; item processing stays in IngestItemProcessor.

from __future__ import annotations

import time
from typing import Any

from apps.knowledge.domain.ingest_run import IngestRun
from core.kernel.interface.observability import observe_metric as observe_platform_metric
from core.kernel.interface.observability import observability_scope


class IngestRunProcessor:
    def __init__(self, facade: Any, *, item_processor: Any) -> None:
        self._facade = facade
        self._item_processor = item_processor

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

    def process_run(self, run_id: str, *, auto_refresh_semantic_index: bool = True) -> IngestRun:
        run_started = time.perf_counter()
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise ValueError("Ingest run not found")
        started_run = self._ingest_runs().mark_run_processing(run)
        items = self._ingest_item_store.list_for_run(run_id)
        with observability_scope(ingest_run_id=run_id, corpus_uuid=started_run.corpus_uuid):
            for item in items:
                try:
                    if not self._item_processor.process_single_item(
                        started_run=started_run,
                        item=item,
                        ingest_input=self._ingest_input_store.get_for_item(item.id),
                    ):
                        break
                finally:
                    started_run = self._ingest_runs().recalculate_progress(run_id)
        final_run = self._ingest_runs().mark_run_completed_if_ready(run_id)
        if auto_refresh_semantic_index:
            self._auto_refresh_semantic_block_index_after_ingest(final_run)
        final_run = self._ingest_runs().mark_run_completed_if_ready(run_id)
        self._log_ingest_trace_summary(run_id)
        observe_platform_metric(
            "ingest_job_duration_seconds",
            time.perf_counter() - run_started,
            unit="seconds",
            tags={"status": str(final_run.status or "unknown")},
        )
        return final_run


__all__ = ["IngestRunProcessor"]
