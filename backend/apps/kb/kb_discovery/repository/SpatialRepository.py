from __future__ import annotations

from sqlalchemy import delete, func, select

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
            return int(
                session.execute(
                    select(func.count(SpatialMention.id)).where(SpatialMention.job_id == job_id)
                ).scalar()
                or 0
            )

    def list_for_chunks(self, job_id: str, chunk_ids: list[str]) -> list[SpatialMention]:
        if not chunk_ids:
            return []
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(SpatialMention).where(
                        SpatialMention.job_id == job_id,
                        SpatialMention.chunk_id.in_(chunk_ids),
                    )
                ).scalars()
            )


__all__ = ["SpatialRepository"]
