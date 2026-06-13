from __future__ import annotations

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship


class RelationshipRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, relationships: list[KnowledgeRelationship]) -> int:
        with self._session_factory() as session:
            session.execute(delete(KnowledgeRelationship).where(KnowledgeRelationship.job_id == job_id))
            for relationship in relationships:
                session.add(relationship)
            session.commit()
            return len(relationships)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(
                        select(KnowledgeRelationship.id).where(KnowledgeRelationship.job_id == job_id)
                    ).scalars()
                )
            )


__all__ = ["RelationshipRepository"]
