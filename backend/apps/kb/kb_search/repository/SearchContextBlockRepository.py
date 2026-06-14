from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_search.orm.SearchContextBlock import SearchContextBlock


class SearchContextBlockRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def bulk_create(self, rows: list[SearchContextBlock]) -> None:
        if not rows:
            return
        with self._session_factory() as session:
            session.add_all(rows)
            session.commit()

    def list_for_run(self, query_run_id: str) -> list[SearchContextBlock]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(SearchContextBlock)
                    .where(SearchContextBlock.query_run_id == query_run_id)
                    .order_by(SearchContextBlock.rank.asc())
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows


__all__ = ["SearchContextBlockRepository"]
