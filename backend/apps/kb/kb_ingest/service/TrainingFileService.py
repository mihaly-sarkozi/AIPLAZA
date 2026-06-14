from __future__ import annotations

# backend/apps/kb/kb_ingest/service/TrainingFileService.py
# Feladat: Fájlos tanítás beküldése (validáció + storage + DB), majd understanding esemény.
# Sárközi Mihály - 2026.06.07

from fastapi import UploadFile

from apps.kb.kb_ingest.config.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.kb_ingest.config import MetricsConf
from apps.kb.kb_ingest.dto.TrainingFileItemSave import TrainingFileItemSave
from apps.kb.kb_ingest.dto.TrainingFilesBatchSave import TrainingFilesBatchSave
from apps.kb.kb_ingest.dto.TrainingTextResult import TrainingTextResult
from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_ingest.enums.TrainingMetric import TrainingMetric
from apps.kb.kb_ingest.errors.TrainingDuplicateError import TrainingDuplicateError
from apps.kb.kb_ingest.errors.TrainingQueueUnavailableError import TrainingQueueUnavailableError
from apps.kb.kb_ingest.events.understanding_requested_event import add_understanding_requested_event
from apps.kb.kb_ingest.ports.ReadingPolicyPort import ReadingPolicyPort
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository
from apps.kb.kb_ingest.service.training_file_upload import prepare_training_upload
from apps.kb.kb_ingest.validation.TrainingValidationError import TrainingValidationError
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.ports.FileStorageInterface import FileStorageInterface
from apps.kb.shared.ids import new_id
from core.kernel.jobs.errors import JobQueueUnavailableError
from shared.utils.hash import sha256_bytes


class TrainingFileService:
    def __init__(
        self,
        *,
        repository: TrainingRepository,
        file_storage: FileStorageInterface,
        config: ReadingConfig | None = None,
        policy: ReadingPolicyPort | None = None,
    ) -> None:
        self._repository = repository
        self._file_storage = file_storage
        self._config = config or DEFAULT_READING_CONFIG
        self._policy = policy

    async def submit_file_training(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        created_by: int,
        uploads: list[UploadFile],
        usage_tenant: object | None = None,
    ) -> TrainingTextResult:
        self._repository.ensure_active_knowledge_base(knowledge_base_id)
        if not uploads:
            raise TrainingValidationError(TrainingErrorCode.VALIDATION_ERROR, reason="No files provided.")
        if len(uploads) > self._config.max_files_per_batch:
            raise TrainingValidationError(
                TrainingErrorCode.VALIDATION_ERROR,
                reason=f"Too many files in one upload. Max: {self._config.max_files_per_batch}.",
            )

        batch_id = new_id("training_batch")
        item_saves: list[TrainingFileItemSave] = []
        total_size = 0

        for upload in uploads:
            prepared = await prepare_training_upload(upload, config=self._config)
            next_total = total_size + len(prepared.raw)
            if next_total > self._config.max_total_upload_bytes:
                raise TrainingValidationError(
                    TrainingErrorCode.VALIDATION_ERROR,
                    reason=(
                        f"Total upload size exceeds limit "
                        f"({self._config.max_total_upload_bytes // (1024 * 1024)} MB)."
                    ),
                )
            total_size = next_total

            content_hash = sha256_bytes(prepared.raw)
            duplicate = self._repository.find_duplicate_by_content_hash(knowledge_base_id, content_hash)
            if duplicate is not None:
                raise TrainingDuplicateError()

            item_id = new_id("training_item")
            mime_type = prepared.mime_type or "application/octet-stream"
            raw_ref = self._file_storage.store_file(
                tenant=tenant,
                knowledge_base_id=knowledge_base_id,
                training_batch_id=batch_id,
                training_item_id=item_id,
                data=prepared.raw,
                filename=prepared.filename,
                content_type=mime_type,
            )
            MetricsConf.increment(TrainingMetric.STORAGE_WRITE, input_type="file")
            item_saves.append(
                TrainingFileItemSave(
                    item_id=item_id,
                    content_hash=content_hash,
                    title=prepared.filename,
                    raw_ref=raw_ref,
                    mime_type=mime_type,
                    size_bytes=len(prepared.raw),
                    metadata={
                        "char_count": prepared.char_count,
                        "original_filename": prepared.filename,
                    },
                )
            )

        ingest = self._repository.save_training_files_batch(
            TrainingFilesBatchSave(
                batch_id=batch_id,
                tenant=tenant,
                knowledge_base_id=knowledge_base_id,
                created_by=created_by,
                items=item_saves,
            )
        )
        if self._policy is not None and usage_tenant is not None:
            total_chars = sum(int(item.metadata.get("char_count") or 0) for item in item_saves)
            self._policy.record_training_usage(
                usage_tenant,
                char_count=total_chars,
                storage_bytes=total_size,
            )

        try:
            for item in item_saves:
                add_understanding_requested_event(
                    tenant_slug=tenant,
                    training_batch_id=ingest.batch_id,
                    training_item_id=item.item_id,
                    knowledge_base_id=knowledge_base_id,
                    created_by=created_by,
                    input_type="file",
                )
        except (JobQueueUnavailableError, RuntimeError) as exc:
            raise TrainingQueueUnavailableError() from exc

        return TrainingTextResult(
            training_batch_id=ingest.batch_id,
            status=TrainingBatchStatus.COMPLETED,
            created_at=ingest.created_at,
            completed_at=ingest.completed_at,
        )


__all__ = ["TrainingFileService"]
