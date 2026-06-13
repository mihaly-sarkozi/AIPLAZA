from __future__ import annotations

from sqlalchemy import delete, select

from apps.kb.kb_discovery.orm.ProcessMention import ProcessMention


class ProcessRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_job(self, job_id: str, mentions: list[ProcessMention]) -> int:
        with self._session_factory() as session:
            session.execute(delete(ProcessMention).where(ProcessMention.job_id == job_id))
            for mention in mentions:
                session.add(mention)
            session.commit()
            return len(mentions)

    def count_for_job(self, job_id: str) -> int:
        with self._session_factory() as session:
            return len(
                list(
                    session.execute(
                        select(ProcessMention.id).where(ProcessMention.job_id == job_id)
                    ).scalars()
                )
            )

    def list_for_chunks(self, job_id: str, chunk_ids: list[str]) -> list[ProcessMention]:
        if not chunk_ids:
            return []
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(ProcessMention).where(
                        ProcessMention.job_id == job_id,
                        ProcessMention.chunk_id.in_(chunk_ids),
                    )
                ).scalars()
            )


__all__ = ["ProcessRepository"]
