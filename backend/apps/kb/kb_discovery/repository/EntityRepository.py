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

    def list_for_document(self, document_id: str) -> list[KnowledgeEntity]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(KnowledgeEntity).where(KnowledgeEntity.document_id == document_id)
                ).scalars()
            )

    def list_for_chunks(self, document_id: str, chunk_ids: list[str]) -> list[KnowledgeEntity]:
        if not chunk_ids:
            return []
        chunk_id_set = set(chunk_ids)
        return [
            entity
            for entity in self.list_for_document(document_id)
            if chunk_id_set.intersection(entity.chunk_ids or [])
        ]


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

    def list_by_job_grouped_by_chunk(self, job_id: str) -> dict[str, list[EntityMention]]:
        with self._session_factory() as session:
            rows = list(
                session.execute(select(EntityMention).where(EntityMention.job_id == job_id)).scalars()
            )
        grouped: dict[str, list[EntityMention]] = {}
        for row in rows:
            grouped.setdefault(row.chunk_id, []).append(row)
        return grouped

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(
                        select(EntityMention.id).where(EntityMention.job_id == job_id)
                    ).scalars()
                )
            )


__all__ = ["EntityMentionRepository", "EntityRepository"]
