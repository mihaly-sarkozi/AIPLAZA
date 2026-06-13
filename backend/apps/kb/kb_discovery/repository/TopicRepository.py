from __future__ import annotations

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic


class TopicRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, topics: list[KnowledgeTopic]) -> int:
        with self._session_factory() as session:
            session.execute(delete(KnowledgeTopic).where(KnowledgeTopic.job_id == job_id))
            for topic in topics:
                session.add(topic)
            session.commit()
            return len(topics)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(select(KnowledgeTopic.id).where(KnowledgeTopic.job_id == job_id))
                    .scalars()
                )
            )


__all__ = ["TopicRepository"]
