from __future__ import annotations

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.KnowledgeScore import KnowledgeScore


class ScoreRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_chunks(self, chunk_ids: list[str], scores: list[KnowledgeScore]) -> int:
        with self._session_factory() as session:
            if chunk_ids:
                session.execute(delete(KnowledgeScore).where(KnowledgeScore.chunk_id.in_(chunk_ids)))
            for score in scores:
                session.add(score)
            session.commit()
            return len(scores)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(select(KnowledgeScore.id).where(KnowledgeScore.job_id == job_id))
                    .scalars()
                )
            )


__all__ = ["ScoreRepository"]
