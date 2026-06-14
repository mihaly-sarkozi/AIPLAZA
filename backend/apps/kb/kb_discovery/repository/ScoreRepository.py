from __future__ import annotations

from sqlalchemy import delete, func, select

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
            return int(
                session.execute(select(func.count(KnowledgeScore.id)).where(KnowledgeScore.job_id == job_id))
                .scalar()
                or 0
            )

    def get_for_chunks(self, job_id: str, chunk_ids: list[str]) -> dict[str, KnowledgeScore]:
        if not chunk_ids:
            return {}
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeScore).where(
                        KnowledgeScore.job_id == job_id,
                        KnowledgeScore.chunk_id.in_(chunk_ids),
                    )
                ).scalars()
            )
        return {row.chunk_id: row for row in rows}


__all__ = ["ScoreRepository"]
