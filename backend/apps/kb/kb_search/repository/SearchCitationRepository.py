from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_search.orm.SearchCitation import SearchCitation


class SearchCitationRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def bulk_create(self, rows: list[SearchCitation]) -> None:
        if not rows:
            return
        with self._session_factory() as session:
            session.add_all(rows)
            session.commit()

    def list_for_run(self, query_run_id: str) -> list[SearchCitation]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(SearchCitation)
                    .where(SearchCitation.query_run_id == query_run_id)
                    .order_by(SearchCitation.display_order.asc())
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows

    def get_by_source_id(self, query_run_id: str, source_id: str) -> SearchCitation | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(SearchCitation)
                    .where(
                        SearchCitation.query_run_id == query_run_id,
                        SearchCitation.source_id == source_id,
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row


__all__ = ["SearchCitationRepository"]
