from __future__ import annotations

from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment


class EnrichmentRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, rows: list[KnowledgeEnrichment]) -> None:
        with self._session_factory() as session:
            session.query(KnowledgeEnrichment).filter(KnowledgeEnrichment.job_id == job_id).delete()
            session.add_all(rows)
            session.commit()

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return session.query(KnowledgeEnrichment).filter(KnowledgeEnrichment.job_id == job_id).count()


__all__ = ["EnrichmentRepository"]
