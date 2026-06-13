from __future__ import annotations

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.SpatialMention import SpatialMention


class SpatialRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, mentions: list[SpatialMention]) -> int:
        with self._session_factory() as session:
            session.execute(delete(SpatialMention).where(SpatialMention.job_id == job_id))
            for mention in mentions:
                session.add(mention)
            session.commit()
            return len(mentions)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(
                        select(SpatialMention.id).where(SpatialMention.job_id == job_id)
                    ).scalars()
                )
            )


__all__ = ["SpatialRepository"]
