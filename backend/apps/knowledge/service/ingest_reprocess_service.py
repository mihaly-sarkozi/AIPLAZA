from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.errors import IngestItemNotFound, IngestItemReprocessConflict, IngestRunNotFound
from apps.knowledge.service.facade_helpers import utcnow as utcnow
from apps.knowledge.service.ingest_item_cleanup_service import IngestItemCleanupService


class IngestReprocessService:
    def __init__(
        self,
        *,
        ingest_item_store: Any,
        ingest_run_store: Any,
        cleanup_service: IngestItemCleanupService,
        refresh_ingest_run: Callable[[str], IngestRun],
        is_stale_parser_processing: Callable[..., bool],
        record_ingest_event: Callable[..., Any],
    ) -> None:
        self._ingest_item_store = ingest_item_store
        self._ingest_run_store = ingest_run_store
        self._cleanup_service = cleanup_service
        self._refresh_ingest_run = refresh_ingest_run
        self._is_stale_parser_processing = is_stale_parser_processing
        self._record_ingest_event = record_ingest_event

    @staticmethod
    def reset_reprocess_item_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(metadata)
        for key in (
            "source_id",
            "parser_run_id",
            "document_id",
            "sentence_count",
            "paragraph_count",
            "interpretation_run_id",
            "handoff_target",
        ):
            cleaned.pop(key, None)
        cleaned.pop("processing_summary", None)
        cleaned["reprocess_requested_at"] = utcnow().isoformat()
        return cleaned

    def request_reprocess(self, item_id: str, *, current_user_id: int | None = None) -> IngestRun:
        item = self._ingest_item_store.get(item_id)
        if item is None:
            raise IngestItemNotFound()
        run = self._ingest_run_store.get(item.ingest_run_id)
        if run is None:
            raise IngestRunNotFound()
        if run.status in {"queued", "processing"}:
            run = self._refresh_ingest_run(run.id)
            item = self._ingest_item_store.get(item_id) or item
        source_id = str(item.source_id or item.metadata.get("source_id") or "").strip()
        stale = bool(source_id) and self._is_stale_parser_processing(source_id, updated_at=item.updated_at)
        if (run.status in {"queued", "processing"} or item.status == "processing") and not stale:
            raise IngestItemReprocessConflict(
                "Az ingest rekord jelenleg feldolgozás alatt áll, ezért most nem indítható újra."
            )

        self._cleanup_service.delete_ingest_item_outputs(item)
        reset_item = self._ingest_item_store.update(
            replace(
                item,
                status="received",
                progress_message="Újrafeldolgozás ütemezve.",
                result_message=None,
                error_code=None,
                error_message=None,
                duplicate_of_item_id=None,
                duplicate_of_source_id=None,
                parser_job_id=None,
                source_id=None,
                content_hash=None,
                idempotency_key=None,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
                retry_count=0,
                dead_letter_reason=None,
                started_at=None,
                completed_at=None,
                updated_at=utcnow(),
                metadata=self.reset_reprocess_item_metadata(item.metadata),
            )
        )
        self._record_ingest_event(
            run_id=run.id,
            item_id=reset_item.id,
            event_type="reprocess_requested",
            status="ok",
            message="A korábbi forrás törölve lett, az ingest item újrafeldolgozásra vár.",
            created_by=current_user_id,
        )
        return self._refresh_ingest_run(run.id)


__all__ = ["IngestReprocessService"]
