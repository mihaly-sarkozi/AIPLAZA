from __future__ import annotations

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.dto.IndexingDiagnosticsResponse import IndexingDiagnosticsResponse
from apps.kb.kb_indexing.ports.reader_ports import EmbeddingJobReaderPort, KnowledgeBaseReaderPort
from apps.kb.kb_indexing.repository.IndexVerificationRepository import IndexVerificationRepository
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from sqlalchemy import desc, select

from apps.kb.kb_indexing.orm.IndexingJob import IndexingJob


class IndexingDiagnosticsService:
    def __init__(
        self,
        *,
        session_factory,
        indexing_job_repository: IndexingJobRepository,
        indexed_chunk_repository: IndexedChunkRepository,
        verification_repository: IndexVerificationRepository,
        embedding_job_reader: EmbeddingJobReaderPort,
        knowledge_base_reader: KnowledgeBaseReaderPort,
        metrics_repository: ProcessingMetricsRepository,
        qdrant_adapter: QdrantAdapter,
    ) -> None:
        self._session_factory = session_factory
        self._indexing_jobs = indexing_job_repository
        self._indexed_chunks = indexed_chunk_repository
        self._verifications = verification_repository
        self._embedding_jobs = embedding_job_reader
        self._knowledge_bases = knowledge_base_reader
        self._metrics = metrics_repository
        self._qdrant = qdrant_adapter

    def for_knowledge_base(self, knowledge_base_id: str) -> IndexingDiagnosticsResponse:
        job = self._latest_indexing_job(knowledge_base_id=knowledge_base_id)
        training_item_id = job.training_item_id if job else None
        return self._build(knowledge_base_id, training_item_id, job)

    def for_training_item(self, knowledge_base_id: str, training_item_id: str) -> IndexingDiagnosticsResponse:
        job = self._latest_indexing_job(
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
        )
        return self._build(knowledge_base_id, training_item_id, job)

    def _build(
        self,
        knowledge_base_id: str,
        training_item_id: str | None,
        indexing_job,
    ) -> IndexingDiagnosticsResponse:
        embedding_job = None
        verification = None
        collection_name = self._knowledge_bases.get_qdrant_collection_name(knowledge_base_id) or ""

        if indexing_job is not None:
            embedding_job = self._embedding_jobs.get_job(indexing_job.embedding_job_id)
            verification = self._verifications.get_latest_for_indexing_job(indexing_job.id)
            collection_name = indexing_job.collection_name or collection_name

        metrics = self._metrics.get_for_knowledge_base(knowledge_base_id)
        meta = dict(metrics.metadata_json or {}) if metrics else {}

        indexed_count = 0
        failed_count = 0
        if indexing_job is not None:
            counts = self._indexed_chunks.count_by_status(indexing_job.id)
            indexed_count = counts.get("INDEXED", 0)
            failed_count = counts.get("FAILED", 0)

        collection_exists = bool(collection_name) and self._qdrant.collection_exists(collection_name)
        blocking = [
            reason
            for reason in (
                meta.get("blocking_reasons") if isinstance(meta.get("blocking_reasons"), list) else []
            )
        ]

        return IndexingDiagnosticsResponse(
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            embedding={
                "job_status": str((embedding_job or {}).get("status") or "UNKNOWN"),
                "embeddings_total": int((embedding_job or {}).get("chunks_embedded") or 0),
                "failed_embeddings": int((embedding_job or {}).get("chunks_failed") or 0),
                "model": str((embedding_job or {}).get("model_name") or ""),
                "dimension": int((embedding_job or {}).get("embedding_dimension") or 0),
            },
            indexing={
                "job_status": str(getattr(indexing_job, "status", None) or "UNKNOWN"),
                "indexed_chunks": indexed_count,
                "failed_chunks": failed_count,
                "collection_name": collection_name,
                "job_id": getattr(indexing_job, "id", None),
            },
            qdrant={
                "collection_exists": collection_exists,
                "points_expected": int(getattr(verification, "expected_points", 0) or 0),
                "points_verified": int(getattr(verification, "verified_points", 0) or 0),
                "missing_points": int(getattr(verification, "missing_points", 0) or 0),
                "payload_mismatches": int(getattr(verification, "payload_mismatches", 0) or 0),
                "vector_hash_mismatches": int(getattr(verification, "vector_hash_mismatches", 0) or 0),
                "verification_status": str(getattr(verification, "status", None) or ""),
            },
            readiness={
                "ready_for_search": bool(meta.get("ready_for_search")),
                "qdrant_verified": bool(meta.get("qdrant_verified")),
                "blocking_issues": blocking,
            },
        )

    def _latest_indexing_job(
        self,
        *,
        knowledge_base_id: str,
        training_item_id: str | None = None,
    ):
        with self._session_factory() as session:
            query = select(IndexingJob).where(IndexingJob.knowledge_base_id == knowledge_base_id)
            if training_item_id:
                query = query.where(IndexingJob.training_item_id == training_item_id)
            row = session.execute(query.order_by(desc(IndexingJob.created_at)).limit(1)).scalars().first()
            if row is not None:
                session.expunge(row)
            return row


__all__ = ["IndexingDiagnosticsService"]
