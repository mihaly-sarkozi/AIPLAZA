from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/ScoreRepository.py
# Feladat: Pontszám perzisztencia, chunk-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, select

from apps.kb.kb_understanding.orm.KnowledgeScore import KnowledgeScore


class ScoreRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_chunks(self, chunk_ids: list[str], scores: list[KnowledgeScore]) -> int:
        with self._session_factory() as session:
            if chunk_ids:
                session.execute(
                    delete(KnowledgeScore).where(KnowledgeScore.chunk_id.in_(chunk_ids))
                )
            for score in scores:
                session.add(score)
            session.commit()
            return len(scores)

    def list_for_chunks(self, chunk_ids: list[str]) -> list[KnowledgeScore]:
        if not chunk_ids:
            return []
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeScore).where(KnowledgeScore.chunk_id.in_(chunk_ids))
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows


__all__ = ["ScoreRepository"]
