from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/RelationshipRepository.py
# Feladat: Kapcsolat perzisztencia, job-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, select

from apps.kb.kb_understanding.orm.KnowledgeRelationship import KnowledgeRelationship


class RelationshipRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, relationships: list[KnowledgeRelationship]) -> int:
        with self._session_factory() as session:
            session.execute(
                delete(KnowledgeRelationship).where(KnowledgeRelationship.job_id == job_id)
            )
            for relationship in relationships:
                session.add(relationship)
            session.commit()
            return len(relationships)

    def list_for_job(self, job_id: str) -> list[KnowledgeRelationship]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeRelationship).where(KnowledgeRelationship.job_id == job_id)
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows


__all__ = ["RelationshipRepository"]
