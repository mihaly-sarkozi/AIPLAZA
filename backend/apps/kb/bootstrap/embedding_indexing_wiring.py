from __future__ import annotations

from apps.kb.kb_embedding.dto.EmbeddingChunkDto import EmbeddingChunkDto
from apps.kb.kb_embedding.dto.EmbeddingDiscoveryBundleDto import EmbeddingDiscoveryBundleDto
from apps.kb.kb_indexing.dto.IndexingDiscoveryBundleDto import IndexingDiscoveryBundleDto
from apps.kb.shared.contracts import DiscoveryChunkSnapshot, IndexingChunkSnapshot, IndexingEmbeddingSnapshot


class EmbeddingChunkReaderAdapter:
    def __init__(self, chunk_repository) -> None:
        self._chunk_repository = chunk_repository

    def list_for_document(self, document_id: str) -> list[EmbeddingChunkDto]:
        chunks = self._chunk_repository.list_for_document(document_id)
        return [
            EmbeddingChunkDto(
                chunk_id=chunk.id,
                text=chunk.text,
                chunk_type=str(chunk.chunk_type or "text"),
                order_index=int(chunk.order_index or 0),
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                language_code=chunk.language_code,
                language_confidence=chunk.language_confidence,
                metadata=dict(chunk.metadata_json or {}),
            )
            for chunk in chunks
        ]


class IndexingChunkReaderAdapter:
    def __init__(self, chunk_repository) -> None:
        self._chunk_repository = chunk_repository

    def list_for_document(self, document_id: str) -> list[IndexingChunkSnapshot]:
        chunks = self._chunk_repository.list_for_document(document_id)
        return [
            IndexingChunkSnapshot(
                chunk_id=chunk.id,
                text=chunk.text,
                chunk_type=str(chunk.chunk_type or "text"),
                order_index=int(chunk.order_index or 0),
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                language_code=chunk.language_code,
                language_confidence=chunk.language_confidence,
                metadata_json=dict(chunk.metadata_json or {}),
            )
            for chunk in chunks
        ]


class DiscoveryJobReaderAdapter:
    def __init__(self, job_repository, understanding_job_reader=None) -> None:
        self._job_repository = job_repository
        self._understanding_job_reader = understanding_job_reader

    def get_job(self, discovery_job_id: str) -> dict | None:
        job = self._job_repository.get_job(discovery_job_id)
        if job is None:
            return None
        metadata = dict(job.metadata_json or {})
        title = job.training_item_id
        source_type = metadata.get("source_type") or "text"
        if self._understanding_job_reader is not None:
            und = self._understanding_job_reader.get_job(job.understanding_job_id)
            if und is not None:
                title = str(und.get("title") or title)
                source_type = str(und.get("source_type") or source_type)
        return {
            "id": job.id,
            "status": job.status,
            "understanding_job_id": job.understanding_job_id,
            "training_item_id": job.training_item_id,
            "training_batch_id": job.training_batch_id,
            "knowledge_base_id": job.knowledge_base_id,
            "title": title,
            "source_type": source_type,
        }


class EmbeddingDiscoveryBundleReaderAdapter:
    def __init__(self, bundle_repository) -> None:
        self._bundle_repository = bundle_repository

    def get_bundles_for_chunks(
        self,
        discovery_job_id: str,
        training_item_id: str,
        chunk_ids: list[str],
    ) -> dict[str, EmbeddingDiscoveryBundleDto]:
        raw = self._bundle_repository.get_bundle_for_chunks(
            discovery_job_id,
            training_item_id,
            chunk_ids,
        )
        result: dict[str, EmbeddingDiscoveryBundleDto] = {}
        for chunk_id, bundle in raw.items():
            enrichment = bundle.enrichment
            heading_path = None
            if enrichment and enrichment.metadata_json:
                heading_path = enrichment.metadata_json.get("heading_path")
            keywords = tuple(
                kw.display_term or kw.term
                for kw in sorted(bundle.keywords, key=lambda k: (-k.score, k.rank))
            )
            topics = tuple(
                topic.display_name or topic.normalized_topic or topic.topic_key
                for topic in sorted(bundle.topics, key=lambda t: (-t.score, t.topic_key))
            )
            entities = tuple(
                entity.name
                for entity in sorted(bundle.entities, key=lambda e: (-e.confidence, e.name))
            )
            process_steps = tuple(
                mention.step_text
                for mention in sorted(
                    bundle.process_mentions,
                    key=lambda p: (p.step_order or 0, p.step_text),
                )
                if mention.step_text
            )
            result[chunk_id] = EmbeddingDiscoveryBundleDto(
                chunk_id=chunk_id,
                language_code=bundle.language_code or (
                    enrichment.language_code if enrichment else None
                ),
                content_type=enrichment.content_type if enrichment else None,
                section_title=enrichment.metadata_json.get("section_title") if enrichment else None,
                heading_path=heading_path,
                keywords=keywords,
                topics=topics,
                entities=entities,
                process_steps=process_steps,
            )
        return result


class IndexingDiscoveryBundleReaderAdapter:
    def __init__(self, bundle_repository, chunk_repository) -> None:
        self._bundle_repository = bundle_repository
        self._chunk_repository = chunk_repository

    def get_indexing_bundles_for_chunks(
        self,
        discovery_job_id: str,
        training_item_id: str,
        chunk_ids: list[str],
    ) -> dict[str, IndexingDiscoveryBundleDto]:
        raw = self._bundle_repository.get_bundle_for_chunks(
            discovery_job_id,
            training_item_id,
            chunk_ids,
        )
        chunks = {
            chunk.id: chunk
            for chunk in self._chunk_repository.list_for_document(training_item_id)
        }
        result: dict[str, IndexingDiscoveryBundleDto] = {}
        for chunk_id, bundle in raw.items():
            enrichment = bundle.enrichment
            chunk = chunks.get(chunk_id)
            heading_path = None
            if enrichment and enrichment.metadata_json:
                heading_path = enrichment.metadata_json.get("heading_path")
            keywords = [
                kw.display_term or kw.term
                for kw in sorted(bundle.keywords, key=lambda k: (-k.score, k.rank))
            ]
            topics = [
                topic.display_name or topic.normalized_topic or topic.topic_key
                for topic in sorted(bundle.topics, key=lambda t: (-t.score, t.topic_key))
            ]
            entities = [
                entity.name
                for entity in sorted(bundle.entities, key=lambda e: (-e.confidence, e.name))
            ]
            temporal = [
                {
                    "text": mention.raw_text,
                    "type": mention.temporal_type,
                    "start": mention.normalized_start,
                    "end": mention.normalized_end,
                }
                for mention in bundle.temporal_mentions
            ]
            spatial = [
                {
                    "text": mention.raw_text,
                    "type": mention.location_type,
                }
                for mention in bundle.spatial_mentions
            ]
            process = [
                {
                    "process_name": mention.process_name,
                    "step_text": mention.step_text,
                    "step_order": mention.step_order,
                }
                for mention in bundle.process_mentions
            ]
            relationships = [
                {
                    "type": rel.relation,
                    "from_type": rel.from_type,
                    "from_id": rel.from_id,
                    "to_type": rel.to_type,
                    "to_id": rel.to_id,
                    "weight": rel.weight,
                }
                for rel in bundle.relationships[:10]
            ]
            score = bundle.score
            result[chunk_id] = IndexingDiscoveryBundleDto(
                chunk_id=chunk_id,
                language_code=bundle.language_code or (
                    enrichment.language_code if enrichment else None
                ),
                language_confidence=enrichment.language_confidence if enrichment else None,
                content_type=enrichment.content_type if enrichment else None,
                content_type_confidence=enrichment.content_type_confidence if enrichment else None,
                section_title=chunk.section_title if chunk else None,
                heading_path=heading_path,
                text_preview=(enrichment.preview_text if enrichment else (chunk.text if chunk else "")),
                page_numbers=[chunk.page_number] if chunk and chunk.page_number is not None else [],
                source_part_ids=list((chunk.metadata_json or {}).get("source_part_ids") or []),
                keywords=keywords,
                topics=topics,
                entities=entities,
                temporal_mentions=temporal,
                spatial_mentions=spatial,
                process_mentions=process,
                overall_score=score.knowledge_score if score else None,
                score_components=dict(score.components or {}) if score else {},
                relationship_summary=relationships,
                source_type=str(chunk.source_type) if chunk else None,
                document_id=chunk.document_id if chunk else training_item_id,
                created_at=chunk.created_at.isoformat() if chunk and chunk.created_at else None,
                updated_at=chunk.last_processed_at.isoformat() if chunk and chunk.last_processed_at else None,
            )
        return result


class EmbeddingJobReaderAdapter:
    def __init__(self, job_repository, discovery_job_reader) -> None:
        self._job_repository = job_repository
        self._discovery_job_reader = discovery_job_reader

    def get_job(self, embedding_job_id: str) -> dict | None:
        job = self._job_repository.get_job(embedding_job_id)
        if job is None:
            return None
        discovery = self._discovery_job_reader.get_job(job.discovery_job_id) or {}
        return {
            "id": job.id,
            "status": job.status,
            "understanding_job_id": job.understanding_job_id,
            "discovery_job_id": job.discovery_job_id,
            "training_item_id": job.training_item_id,
            "training_batch_id": discovery.get("training_batch_id"),
            "knowledge_base_id": job.knowledge_base_id,
            "chunks_embedded": job.chunks_embedded,
            "embedding_dimension": job.embedding_dimension,
            "title": discovery.get("title"),
            "source_type": discovery.get("source_type"),
        }


class EmbeddingRecordReaderAdapter:
    def __init__(self, embedding_repository) -> None:
        self._repository = embedding_repository

    def list_successful_for_job(self, embedding_job_id: str) -> list[IndexingEmbeddingSnapshot]:
        rows = self._repository.list_for_job(embedding_job_id, status="COMPLETED")
        return [
            IndexingEmbeddingSnapshot(
                id=row.id,
                chunk_id=row.chunk_id,
                embedding_vector=tuple(row.embedding_vector or []),
                vector_hash=row.vector_hash,
                embedding_dimension=int(row.embedding_dimension or 0),
                status=row.status,
            )
            for row in rows
            if row.embedding_vector
        ]


class KnowledgeBaseReaderAdapter:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get_qdrant_collection_name(self, knowledge_base_id: str) -> str | None:
        from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
        from sqlalchemy import select

        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM.qdrant_collection_name)
                .where(
                    KnowledgeBaseORM.uuid == knowledge_base_id,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
                .limit(1)
            ).scalar_one_or_none()
        if row is None:
            return None
        return str(row) or None

    def exists(self, knowledge_base_id: str) -> bool:
        from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
        from sqlalchemy import select

        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM.id)
                .where(
                    KnowledgeBaseORM.uuid == knowledge_base_id,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
                .limit(1)
            ).scalar_one_or_none()
        return row is not None


__all__ = [
    "DiscoveryJobReaderAdapter",
    "EmbeddingChunkReaderAdapter",
    "EmbeddingDiscoveryBundleReaderAdapter",
    "EmbeddingJobReaderAdapter",
    "EmbeddingRecordReaderAdapter",
    "IndexingChunkReaderAdapter",
    "IndexingDiscoveryBundleReaderAdapter",
    "KnowledgeBaseReaderAdapter",
]
