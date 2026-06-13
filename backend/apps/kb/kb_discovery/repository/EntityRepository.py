from __future__ import annotations

from sqlalchemy import delete, func, select

from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.orm.KnowledgeEntity import KnowledgeEntity


class EntityRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_document(self, document_id: str, entities: list[KnowledgeEntity]) -> int:
        with self._session_factory() as session:
            session.execute(delete(KnowledgeEntity).where(KnowledgeEntity.document_id == document_id))
            for entity in entities:
                session.add(entity)
            session.commit()
            return len(entities)

    def count_for_document(self, document_id: str) -> int:
        with self._session_factory() as session:
            return int(
                session.execute(
                    select(func.count(KnowledgeEntity.id)).where(
                        KnowledgeEntity.document_id == document_id
                    )
                ).scalar()
                or 0
            )


class EntityMentionRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, mentions: list[EntityMention]) -> int:
        with self._session_factory() as session:
            session.execute(delete(EntityMention).where(EntityMention.job_id == job_id))
            for mention in mentions:
                session.add(mention)
            session.commit()
            return len(mentions)


__all__ = ["EntityMentionRepository", "EntityRepository"]
