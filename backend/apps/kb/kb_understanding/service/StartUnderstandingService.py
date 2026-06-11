from __future__ import annotations

# backend/apps/kb/kb_understanding/service/StartUnderstandingService.py
# Feladat: Megértési feldolgozás indítása egy ingest itemre — item betöltés,
# státusz-ellenőrzés, job létrehozás, pipeline kontextus összeállítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.ports.IngestItemReaderInterface import IngestItemReaderInterface
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import UnderstandingJobRepository


class StartUnderstandingService:
    def __init__(
        self,
        job_repository: UnderstandingJobRepository,
        item_reader: IngestItemReaderInterface,
    ) -> None:
        self._job_repository = job_repository
        self._item_reader = item_reader

    def start(
        self,
        *,
        training_item_id: str,
        training_batch_id: str,
        knowledge_base_id: str,
        tenant_slug: str | None,
        created_by: int | None,
    ) -> UnderstandingJobContext:
        item = self._item_reader.get_item_snapshot(training_item_id)
        if item is None:
            raise UnderstandingNotFoundError(
                UnderstandingErrorCode.ITEM_NOT_FOUND, item_id=training_item_id
            )
        raw_ref = (item.raw_ref or "").strip()
        if not raw_ref:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.RAW_REF_MISSING, item_id=training_item_id
            )
        latest = self._job_repository.get_latest_job_for_item(training_item_id)
        if latest is not None and latest.status == UnderstandingStatus.QUEUED.value:
            # Retry által visszasorolt job — újrahasznosítjuk (idempotens újrafutás).
            job = latest
        else:
            if self._job_repository.has_active_job_for_item(training_item_id):
                raise UnderstandingProcessingError(
                    UnderstandingErrorCode.JOB_ALREADY_RUNNING, item_id=training_item_id
                )
            job = self._job_repository.create_job(
                training_item_id=training_item_id,
                training_batch_id=training_batch_id,
                knowledge_base_id=knowledge_base_id,
                created_by=created_by,
                metadata={"mime_type": item.mime_type, "input_type": item.input_type},
            )
            self._job_repository.set_status(job.id, UnderstandingStatus.QUEUED)
        return UnderstandingJobContext(
            job_id=job.id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            knowledge_base_id=knowledge_base_id,
            tenant_slug=tenant_slug,
            created_by=created_by,
            raw_ref=raw_ref,
            mime_type=item.mime_type,
            source_type=item.input_type,
            file_name=item.original_filename,
            title=item.title,
            content_hash=item.content_hash,
        )


__all__ = ["StartUnderstandingService"]
