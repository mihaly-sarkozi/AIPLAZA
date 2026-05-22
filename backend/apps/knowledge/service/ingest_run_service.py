from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any, Callable

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.ports import IngestItemStorePort, IngestRunStorePort


class IngestRunService:
    def __init__(
        self,
        *,
        ingest_run_store: IngestRunStorePort,
        ingest_item_store: IngestItemStorePort,
        progress_summary_builder: Callable[[IngestRun, list[IngestItem]], dict[str, Any]],
        quality_diagnostics_builder: Callable[[list[IngestItem]], dict[str, Any]],
    ) -> None:
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._progress_summary_builder = progress_summary_builder
        self._quality_diagnostics_builder = quality_diagnostics_builder

    def create_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        input_channel: str,
        batch_size: int,
        pipeline_route: str,
        created_by: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> IngestRun:
        return self._ingest_run_store.create(
            IngestRun(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                input_channel=input_channel,
                status="queued",
                batch_size=batch_size,
                queued_count=batch_size,
                pipeline_route=pipeline_route,
                created_by=created_by,
                metadata=dict(metadata or {}),
            )
        )

    def mark_run_processing(self, run: IngestRun) -> IngestRun:
        return self._ingest_run_store.update(
            replace(
                run,
                status="processing",
                started_at=run.started_at or _utcnow(),
                completed_at=None,
                updated_at=_utcnow(),
            )
        )

    def mark_run_failed(self, *, run: IngestRun, error_message: str, failed_count: int) -> IngestRun:
        return self._ingest_run_store.update(
            replace(
                run,
                status="failed",
                failed_count=max(0, int(failed_count)),
                queued_count=0,
                processing_count=0,
                updated_at=_utcnow(),
                completed_at=_utcnow(),
                metadata={**dict(run.metadata or {}), "error_message": str(error_message or "")},
            )
        )

    def mark_item_processing(
        self,
        item: IngestItem,
        *,
        progress_message: str,
        lease_owner: str = "outbox-worker",
        lease_minutes: int = 15,
    ) -> IngestItem:
        now = _utcnow()
        return self._ingest_item_store.update(
            replace(
                item,
                status="processing",
                progress_message=progress_message,
                started_at=item.started_at or now,
                completed_at=None,
                updated_at=now,
                lease_owner=lease_owner,
                lease_expires_at=now + timedelta(minutes=max(1, int(lease_minutes))),
                heartbeat_at=now,
            )
        )

    def mark_item_failed(
        self,
        item: IngestItem,
        *,
        error_code: str,
        error_message: str,
        progress_message: str,
    ) -> IngestItem:
        retry_count = min(int(item.retry_count or 0) + 1, int(item.max_retries or 3))
        return self._ingest_item_store.update(
            replace(
                item,
                status="failed",
                error_code=error_code,
                error_message=error_message,
                progress_message=progress_message,
                retry_count=retry_count,
                dead_letter_reason=error_message if retry_count >= int(item.max_retries or 3) else None,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=_utcnow(),
                completed_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

    def mark_item_retry(self, item: IngestItem, *, progress_message: str = "Újrapróbálás ütemezve.") -> IngestItem:
        return self._ingest_item_store.update(
            replace(
                item,
                status="queued",
                progress_message=progress_message,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=_utcnow(),
                completed_at=None,
                updated_at=_utcnow(),
            )
        )

    def recalculate_progress(self, run_id: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise ValueError(f"Ingest run not found: {run_id}")
        items = self._ingest_item_store.list_for_run(run_id)
        queued = sum(1 for item in items if item.status in {"received", "validated", "queued"})
        processing = sum(1 for item in items if item.status == "processing")
        completed = sum(1 for item in items if item.status == "completed")
        failed = sum(1 for item in items if item.status == "failed")
        duplicate = sum(1 for item in items if item.status == "duplicate")
        rejected = sum(1 for item in items if item.status == "rejected")
        if processing:
            status = "processing"
        elif failed and (completed or duplicate):
            status = "partial_success"
        elif failed:
            status = "failed"
        elif queued:
            status = "queued"
        else:
            status = "completed"
        summary_run = replace(run, status=status)  # type: ignore[arg-type]
        refreshed = replace(
            run,
            status=status,  # type: ignore[arg-type]
            batch_size=len(items),
            queued_count=queued,
            processing_count=processing,
            completed_count=completed,
            failed_count=failed,
            duplicate_count=duplicate,
            rejected_count=rejected,
            updated_at=_utcnow(),
            completed_at=_utcnow() if status in {"completed", "partial_success", "failed"} and not queued and not processing else None,
            metadata={
                **dict(run.metadata or {}),
                "progress_summary": self._progress_summary_builder(summary_run, items),
                "quality_diagnostics": self._quality_diagnostics_builder(items),
            },
        )
        return self._ingest_run_store.update(refreshed)

    def mark_run_completed_if_ready(self, run_id: str) -> IngestRun:
        return self.recalculate_progress(run_id)


__all__ = ["IngestRunService"]
