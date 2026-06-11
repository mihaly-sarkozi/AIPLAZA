from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/EntityRepository.py
# Feladat: Entitás perzisztencia, dokumentum-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.orm.KnowledgeEntity import KnowledgeEntity


class EntityRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_document(self, document_id: str, entities: list[KnowledgeEntity]) -> int:
        with self._session_factory() as session:
            session.execute(
                delete(KnowledgeEntity).where(KnowledgeEntity.document_id == document_id)
            )
            for entity in entities:
                session.add(entity)
            session.commit()
            return len(entities)

    def list_for_document(self, document_id: str) -> list[KnowledgeEntity]:
        with self._session_factory() as session:
            entities = list(
                session.execute(
                    select(KnowledgeEntity)
                    .where(KnowledgeEntity.document_id == document_id)
                    .order_by(KnowledgeEntity.normalized_name.asc())
                )
                .scalars()
                .all()
            )
            for entity in entities:
                session.expunge(entity)
            return entities

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


__all__ = ["EntityRepository"]
