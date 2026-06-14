from __future__ import annotations

from apps.kb.kb_embedding.dto.EmbeddingChunkDto import EmbeddingChunkDto
from apps.kb.kb_embedding.dto.EmbeddingJobContext import EmbeddingJobContext
from apps.kb.kb_embedding.enums.EmbeddingErrorCode import EmbeddingErrorCode
from apps.kb.kb_embedding.enums.EmbeddingStatus import EmbeddingStatus
from apps.kb.kb_embedding.errors.EmbeddingProcessingError import EmbeddingProcessingError
from apps.kb.kb_embedding.ports.reader_ports import ChunkReaderPort, DiscoveryJobReaderPort
from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
from apps.kb.kb_embedding.service.EmbeddingPipelineService import EmbeddingPipelineService


_ALLOWED_DISCOVERY_STATUSES = frozenset({"ready_for_embedding", "partial"})


class StartEmbeddingService:
    def __init__(
        self,
        job_repository: EmbeddingJobRepository,
        chunk_reader: ChunkReaderPort,
        discovery_job_reader: DiscoveryJobReaderPort,
        pipeline: EmbeddingPipelineService,
    ) -> None:
        self._job_repository = job_repository
        self._chunk_reader = chunk_reader
        self._discovery_job_reader = discovery_job_reader
        self._pipeline = pipeline

    def start(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        understanding_job_id: str,
        discovery_job_id: str,
        created_by: int | None,
    ) -> EmbeddingStatus:
        if self._job_repository.has_active_job_for_discovery(discovery_job_id):
            raise EmbeddingProcessingError(
                EmbeddingErrorCode.JOB_ALREADY_RUNNING.value,
                discovery_job_id=discovery_job_id,
            )

        discovery_job = self._discovery_job_reader.get_job(discovery_job_id)
        if discovery_job is None:
            raise EmbeddingProcessingError(
                EmbeddingErrorCode.DISCOVERY_JOB_NOT_FOUND.value,
                discovery_job_id=discovery_job_id,
            )
        discovery_status = str(discovery_job.get("status") or "")
        if discovery_status not in _ALLOWED_DISCOVERY_STATUSES:
            raise EmbeddingProcessingError(
                EmbeddingErrorCode.DISCOVERY_NOT_READY.value,
                discovery_job_id=discovery_job_id,
                status=discovery_status,
            )

        chunks = self._load_chunks(training_item_id)
        if not chunks:
            job = self._job_repository.create_job(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_item_id=training_item_id,
                understanding_job_id=understanding_job_id,
                discovery_job_id=discovery_job_id,
                created_by=created_by,
                embedding_model=self._pipeline.embedding_model,
                embedding_provider=self._pipeline.embedding_provider,
                embedding_dimension=self._pipeline.embedding_dimension,
                chunks_total=0,
            )
            self._job_repository.mark_finished(
                job.id,
                EmbeddingStatus.FAILED,
                error_code=EmbeddingErrorCode.NO_CHUNKS_FOR_EMBEDDING.value,
                error_message="Nincs chunk embeddinghez",
            )
            return EmbeddingStatus.FAILED

        job = self._job_repository.create_job(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            created_by=created_by,
            embedding_model=self._pipeline.embedding_model,
            embedding_provider=self._pipeline.embedding_provider,
            embedding_dimension=self._pipeline.embedding_dimension,
            chunks_total=len(chunks),
            metadata={"source_type": discovery_job.get("source_type") or "text"},
        )
        ctx = EmbeddingJobContext(
            job_id=job.id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            training_item_id=training_item_id,
            training_batch_id=str(discovery_job.get("training_batch_id") or ""),
            knowledge_base_id=knowledge_base_id,
            tenant_slug=tenant_slug,
            created_by=created_by,
            title=str(discovery_job.get("title") or training_item_id),
            source_type=str(discovery_job.get("source_type") or "text"),
        )
        return self._pipeline.run(ctx, chunks)

    def _load_chunks(self, training_item_id: str) -> list[EmbeddingChunkDto]:
        return self._chunk_reader.list_for_document(training_item_id)


__all__ = ["StartEmbeddingService"]
