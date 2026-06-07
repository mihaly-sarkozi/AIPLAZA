from __future__ import annotations

# backend/apps/kb/kb_training/service/TrainingTextService.py
# Feladat: Szöveges tanítás beküldése (storage + DB), majd understanding esemény.
# Sárközi Mihály - 2026.06.07
#
# Technikai adósság: a nyers anyag storage írás a DB commit előtt történik.
# DB hiba esetén árva raw file maradhat — később: pending DB → storage → accepted.

from apps.kb.kb_training.config.TrainingConf import DEFAULT_TRAINING_CONFIG, TrainingConfig
from apps.kb.kb_training.dto.TextTrainingBatchSave import TextTrainingBatchSave
from apps.kb.kb_training.dto.TrainingTextRequest import TrainingTextRequest
from apps.kb.kb_training.dto.TrainingTextResult import TrainingTextResult
from apps.kb.kb_training.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_training.errors.TrainingDuplicateError import TrainingDuplicateError
from apps.kb.kb_training.errors.TrainingQueueUnavailableError import TrainingQueueUnavailableError
from apps.kb.kb_training.events.understanding_requested_event import add_understanding_requested_event
from apps.kb.kb_training.repository.TrainingRepository import TrainingRepository
from apps.kb.kb_training.storage.TrainingRawWriter import TrainingRawWriter
from apps.kb.kb_training.validation.ValidateText import validate_text
from apps.kb.kb_training.validation.ValidateTitle import normalize_title
from apps.kb.shared.ids import new_id
from core.kernel.jobs.errors import JobQueueUnavailableError
from shared.utils.hash import sha256_text


class TrainingTextService:
    def __init__(
        self,
        *,
        repository: TrainingRepository,
        raw_writer: TrainingRawWriter,
        config: TrainingConfig | None = None,
    ) -> None:
        self._repository = repository
        self._raw_writer = raw_writer
        self._config = config or DEFAULT_TRAINING_CONFIG

    async def submit_text_training(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        created_by: int,
        request: TrainingTextRequest,
    ) -> TrainingTextResult:
        title = normalize_title(request.title, config=self._config)
        text = validate_text(request.content, config=self._config)
        content_hash = sha256_text(text)

        duplicate = self._repository.find_duplicate_by_content_hash(
            knowledge_base_id,
            content_hash,
        )
        if duplicate is not None:
            raise TrainingDuplicateError()

        batch_id = new_id("training_batch")
        item_id = new_id("training_item")
        raw_ref = self._raw_writer.write_text(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=batch_id,
            training_item_id=item_id,
            content=text,
        )

        ingest = self._repository.save_training_text_batch(
            TextTrainingBatchSave(
                batch_id=batch_id,
                item_id=item_id,
                tenant=tenant,
                knowledge_base_id=knowledge_base_id,
                created_by=created_by,
                content_hash=content_hash,
                title=title,
                raw_ref=raw_ref,
                mime_type="text/plain",
                size_bytes=len(text.encode("utf-8")),
                metadata={
                    "char_count": len(text),
                    "text_encoding": "utf-8",
                },
            )
        )

        try:
            add_understanding_requested_event(
                tenant_slug=tenant,
                training_batch_id=ingest.batch_id,
                training_item_id=ingest.item_id,
                knowledge_base_id=knowledge_base_id,
                created_by=created_by,
            )
        except (JobQueueUnavailableError, RuntimeError) as exc:
            raise TrainingQueueUnavailableError() from exc

        return TrainingTextResult(
            training_batch_id=ingest.batch_id,
            status=TrainingBatchStatus.COMPLETED,
        )


__all__ = ["TrainingTextService"]
