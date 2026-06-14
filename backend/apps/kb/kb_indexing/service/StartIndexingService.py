from __future__ import annotations

from apps.kb.kb_indexing.adapters.QdrantConfigValidator import QdrantConfigValidator
from apps.kb.kb_indexing.dto.IndexingJobContext import IndexingJobContext
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.errors.IndexingProcessingError import IndexingProcessingError
from apps.kb.kb_indexing.ports.reader_ports import EmbeddingJobReaderPort, KnowledgeBaseReaderPort
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_indexing.service.IndexingPipelineService import IndexingPipelineService


_ALLOWED_EMBEDDING_STATUSES = frozenset({"COMPLETED", "PARTIAL"})


class StartIndexingService:
    def __init__(
        self,
        job_repository: IndexingJobRepository,
        embedding_job_reader: EmbeddingJobReaderPort,
        knowledge_base_reader: KnowledgeBaseReaderPort,
        pipeline: IndexingPipelineService,
    ) -> None:
        self._job_repository = job_repository
        self._embedding_job_reader = embedding_job_reader
        self._knowledge_base_reader = knowledge_base_reader
        self._pipeline = pipeline

    def start(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        understanding_job_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        created_by: int | None,
    ) -> IndexingStatus:
        if self._job_repository.has_active_job_for_embedding(embedding_job_id):
            raise IndexingProcessingError(
                IndexingErrorCode.JOB_ALREADY_RUNNING.value,
                embedding_job_id=embedding_job_id,
            )

        config_error = QdrantConfigValidator.validate_or_error_code()
        if config_error:
            return self._create_failed_job(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_item_id=training_item_id,
                understanding_job_id=understanding_job_id,
                discovery_job_id=discovery_job_id,
                embedding_job_id=embedding_job_id,
                created_by=created_by,
                error_code=config_error,
            )

        embedding_job = self._embedding_job_reader.get_job(embedding_job_id)
        if embedding_job is None:
            raise IndexingProcessingError(
                IndexingErrorCode.EMBEDDING_JOB_NOT_FOUND.value,
                embedding_job_id=embedding_job_id,
            )
        canonical_kb_id = str(embedding_job.get("knowledge_base_id") or "").strip()
        if canonical_kb_id and canonical_kb_id != knowledge_base_id:
            knowledge_base_id = canonical_kb_id
        embedding_status = str(embedding_job.get("status") or "")
        if embedding_status not in _ALLOWED_EMBEDDING_STATUSES:
            raise IndexingProcessingError(
                IndexingErrorCode.EMBEDDING_NOT_READY.value,
                embedding_job_id=embedding_job_id,
                status=embedding_status,
            )
        if int(embedding_job.get("chunks_embedded") or 0) <= 0:
            self._create_failed_job(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_item_id=training_item_id,
                understanding_job_id=understanding_job_id,
                discovery_job_id=discovery_job_id,
                embedding_job_id=embedding_job_id,
                created_by=created_by,
                error_code=IndexingErrorCode.NO_EMBEDDINGS_FOR_INDEXING.value,
            )
            return IndexingStatus.FAILED

        collection_name = self._knowledge_base_reader.get_qdrant_collection_name(knowledge_base_id)
        if not collection_name:
            raise IndexingProcessingError(
                IndexingErrorCode.QDRANT_COLLECTION_MISSING.value,
                knowledge_base_id=knowledge_base_id,
            )

        vector_size = int(embedding_job.get("embedding_dimension") or 0)
        chunks_total = int(embedding_job.get("chunks_embedded") or 0)

        job = self._job_repository.create_job(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            embedding_job_id=embedding_job_id,
            created_by=created_by,
            collection_name=collection_name,
            vector_size=vector_size,
            distance_metric="cosine",
            chunks_total=chunks_total,
        )
        ctx = IndexingJobContext(
            job_id=job.id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            embedding_job_id=embedding_job_id,
            training_item_id=training_item_id,
            training_batch_id=str(embedding_job.get("training_batch_id") or ""),
            knowledge_base_id=knowledge_base_id,
            tenant_slug=tenant_slug,
            created_by=created_by,
            collection_name=collection_name,
            vector_size=vector_size,
            distance_metric="cosine",
            title=str(embedding_job.get("title") or training_item_id),
            source_type=str(embedding_job.get("source_type") or "text"),
        )
        return self._pipeline.run(ctx)

    def _create_failed_job(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        understanding_job_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        created_by: int | None,
        error_code: str,
    ):
        collection_name = self._knowledge_base_reader.get_qdrant_collection_name(knowledge_base_id) or ""
        job = self._job_repository.create_job(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            embedding_job_id=embedding_job_id,
            created_by=created_by,
            collection_name=collection_name,
            vector_size=0,
            distance_metric="cosine",
            chunks_total=0,
        )
        self._job_repository.mark_finished(
            job.id,
            IndexingStatus.FAILED,
            error_code=error_code,
        )
        return job


__all__ = ["StartIndexingService"]
