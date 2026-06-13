from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.enums.DiscoveryErrorCode import DiscoveryErrorCode
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.errors.DiscoveryNotFoundError import DiscoveryNotFoundError
from apps.kb.kb_discovery.errors.DiscoveryProcessingError import DiscoveryProcessingError
from apps.kb.kb_discovery.ports.ChunkReaderPort import ChunkReaderPort, UnderstandingJobReaderPort
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
from apps.kb.shared.contracts import DiscoveryChunkSnapshot


class StartDiscoveryService:
    def __init__(
        self,
        job_repository: DiscoveryJobRepository,
        chunk_reader: ChunkReaderPort,
        understanding_job_reader: UnderstandingJobReaderPort | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._chunk_reader = chunk_reader
        self._understanding_job_reader = understanding_job_reader

    def start(
        self,
        *,
        understanding_job_id: str,
        training_item_id: str,
        training_batch_id: str,
        knowledge_base_id: str,
        tenant_slug: str | None,
        created_by: int | None,
    ) -> tuple[DiscoveryJobContext, list[DiscoveryChunkDto]]:
        chunks = self._load_chunks(training_item_id)
        if not chunks:
            raise DiscoveryProcessingError(
                DiscoveryErrorCode.CHUNKS_MISSING,
                retryable=True,
                item_id=training_item_id,
            )
        source_type = "text"
        title = training_item_id
        if self._understanding_job_reader is not None:
            und_job = self._understanding_job_reader.get_job(understanding_job_id)
            if und_job is None:
                raise DiscoveryNotFoundError(
                    DiscoveryErrorCode.UNDERSTANDING_JOB_NOT_FOUND,
                    job_id=understanding_job_id,
                )
            source_type = str(und_job.get("source_type") or "text")
            title = str(und_job.get("title") or training_item_id)

        latest = self._job_repository.get_latest_job_for_item(training_item_id)
        if latest is not None and latest.status == DiscoveryStatus.QUEUED.value:
            job = latest
        else:
            if self._job_repository.has_active_job_for_item(training_item_id):
                raise DiscoveryProcessingError(
                    DiscoveryErrorCode.JOB_ALREADY_RUNNING,
                    item_id=training_item_id,
                )
            job = self._job_repository.create_job(
                understanding_job_id=understanding_job_id,
                training_item_id=training_item_id,
                training_batch_id=training_batch_id,
                knowledge_base_id=knowledge_base_id,
                created_by=created_by,
                metadata={"source_type": source_type},
            )
            self._job_repository.set_status(job.id, DiscoveryStatus.QUEUED)
        ctx = DiscoveryJobContext(
            job_id=job.id,
            understanding_job_id=understanding_job_id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            knowledge_base_id=knowledge_base_id,
            tenant_slug=tenant_slug,
            created_by=created_by,
            source_type=source_type,
            title=title,
        )
        return ctx, chunks

    def _load_chunks(self, training_item_id: str) -> list[DiscoveryChunkDto]:
        snapshots = self._chunk_reader.list_for_document(training_item_id)
        return [
            DiscoveryChunkDto(
                chunk_id=snapshot.chunk_id,
                text=snapshot.text,
                chunk_type=snapshot.chunk_type,
                order_index=snapshot.order_index,
                section_title=snapshot.section_title,
                page_number=snapshot.page_number,
                language_code=snapshot.language_code,
                language_confidence=snapshot.language_confidence,
                language_detected_by=snapshot.language_detected_by,
                metadata=dict(snapshot.metadata_json or {}),
            )
            for snapshot in snapshots
        ]


__all__ = ["StartDiscoveryService"]
