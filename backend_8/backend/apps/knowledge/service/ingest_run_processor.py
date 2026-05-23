# backend/apps/knowledge/service/ingest_run_processor.py
# Owns ingest-run level orchestration; item processing stays in IngestItemProcessor.

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.errors import IngestRunNotFound
from core.kernel.interface.observability import observe_metric as observe_platform_metric
from core.kernel.interface.observability import observability_scope


@dataclass(frozen=True)
class IngestRunProcessorDependencies:
    ingest_run_store: Any
    ingest_item_store: Any
    ingest_input_store: Any
    ingest_runs: Any
    auto_refresh_semantic_block_index_after_ingest: Any
    log_ingest_trace_summary: Any


class IngestRunProcessor:
    def __init__(self, dependencies: IngestRunProcessorDependencies, *, item_processor: Any) -> None:
        self._ingest_run_store = getattr(dependencies, "ingest_run_store", getattr(dependencies, "_ingest_run_store", None))
        self._ingest_item_store = getattr(dependencies, "ingest_item_store", getattr(dependencies, "_ingest_item_store", None))
        self._ingest_input_store = getattr(dependencies, "ingest_input_store", getattr(dependencies, "_ingest_input_store", None))
        self._ingest_runs = getattr(dependencies, "ingest_runs", getattr(dependencies, "_ingest_runs", lambda: None))
        self._auto_refresh_semantic_block_index_after_ingest = getattr(
            dependencies,
            "auto_refresh_semantic_block_index_after_ingest",
            getattr(dependencies, "_auto_refresh_semantic_block_index_after_ingest", lambda _run: None),
        )
        self._log_ingest_trace_summary = getattr(
            dependencies,
            "log_ingest_trace_summary",
            getattr(dependencies, "_log_ingest_trace_summary", lambda _run_id: None),
        )
        self._item_processor = item_processor

    def process_run(self, run_id: str, *, auto_refresh_semantic_index: bool = True) -> IngestRun:
        run_started = time.perf_counter()
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise IngestRunNotFound()
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


__all__ = ["IngestRunProcessor", "IngestRunProcessorDependencies"]
