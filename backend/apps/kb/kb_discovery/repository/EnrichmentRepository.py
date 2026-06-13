from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword
from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic


@dataclass(frozen=True)
class EnrichmentBundle:
    chunk_id: str
    enrichment: KnowledgeEnrichment | None
    keywords: tuple[KnowledgeKeyword, ...]
    topics: tuple[KnowledgeTopic, ...]


class EnrichmentRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, rows: list[KnowledgeEnrichment]) -> None:
        with self._session_factory() as session:
            session.execute(delete(KnowledgeEnrichment).where(KnowledgeEnrichment.job_id == job_id))
            session.add_all(rows)
            session.commit()

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(
                        select(KnowledgeEnrichment.id).where(KnowledgeEnrichment.job_id == job_id)
                    ).scalars()
                )
            )

    def get_enrichment_bundle_for_chunks(
        self,
        job_id: str,
        chunk_ids: list[str],
    ) -> dict[str, EnrichmentBundle]:
        if not chunk_ids:
            return {}
        with self._session_factory() as session:
            enrichments = {
                row.chunk_id: row
                for row in session.execute(
                    select(KnowledgeEnrichment).where(
                        KnowledgeEnrichment.job_id == job_id,
                        KnowledgeEnrichment.chunk_id.in_(chunk_ids),
                    )
                ).scalars()
            }
            keywords_by_chunk: dict[str, list[KnowledgeKeyword]] = {chunk_id: [] for chunk_id in chunk_ids}
            for row in session.execute(
                select(KnowledgeKeyword).where(
                    KnowledgeKeyword.job_id == job_id,
                    KnowledgeKeyword.chunk_id.in_(chunk_ids),
                )
            ).scalars():
                keywords_by_chunk.setdefault(row.chunk_id, []).append(row)
            topics_by_chunk: dict[str, list[KnowledgeTopic]] = {chunk_id: [] for chunk_id in chunk_ids}
            for row in session.execute(
                select(KnowledgeTopic).where(
                    KnowledgeTopic.job_id == job_id,
                    KnowledgeTopic.chunk_id.in_(chunk_ids),
                )
            ).scalars():
                topics_by_chunk.setdefault(row.chunk_id, []).append(row)

        return {
            chunk_id: EnrichmentBundle(
                chunk_id=chunk_id,
                enrichment=enrichments.get(chunk_id),
                keywords=tuple(keywords_by_chunk.get(chunk_id, [])),
                topics=tuple(topics_by_chunk.get(chunk_id, [])),
            )
            for chunk_id in chunk_ids
        }


def bundle_to_indexing_payload(bundle: EnrichmentBundle) -> dict[str, Any]:
    enrichment = bundle.enrichment
    if enrichment is None:
        return {}
    return {
        "language_code": enrichment.language_code,
        "content_type": enrichment.content_type,
        "keywords": [item.normalized_term for item in bundle.keywords[:20]],
        "topics": [item.topic_key for item in bundle.topics[:10]],
        "profile_confidence": enrichment.profile_confidence,
    }


__all__ = ["EnrichmentBundle", "EnrichmentRepository", "bundle_to_indexing_payload"]
