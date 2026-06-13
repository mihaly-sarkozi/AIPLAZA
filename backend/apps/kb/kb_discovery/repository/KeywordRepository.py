from __future__ import annotations

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword


class KeywordRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, keywords: list[KnowledgeKeyword]) -> int:
        with self._session_factory() as session:
            session.execute(delete(KnowledgeKeyword).where(KnowledgeKeyword.job_id == job_id))
            for keyword in keywords:
                session.add(keyword)
            session.commit()
            return len(keywords)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(
                        select(KnowledgeKeyword.id).where(KnowledgeKeyword.job_id == job_id)
                    ).scalars()
                )
            )


__all__ = ["KeywordRepository"]
