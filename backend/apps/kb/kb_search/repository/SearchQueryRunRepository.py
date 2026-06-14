from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_search.orm.SearchQueryRun import SearchQueryRun
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class SearchQueryRunRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create(self, run: SearchQueryRun) -> SearchQueryRun:
        with self._session_factory() as session:
            session.add(run)
            session.commit()
            session.refresh(run)
            session.expunge(run)
            return run

    def get(self, run_id: str) -> SearchQueryRun | None:
        with self._session_factory() as session:
            row = session.get(SearchQueryRun, run_id)
            if row is not None:
                session.expunge(row)
            return row

    def update(self, run: SearchQueryRun) -> SearchQueryRun:
        with self._session_factory() as session:
            existing = session.get(SearchQueryRun, run.id)
            if existing is None:
                session.add(run)
            else:
                for column in SearchQueryRun.__table__.columns:
                    name = column.name
                    if name == "id":
                        continue
                    setattr(existing, name, getattr(run, name))
                run = existing
            session.commit()
            session.refresh(run)
            session.expunge(run)
            return run

    def new_run(
        self,
        *,
        tenant_slug: str | None,
        user_id: int | None,
        channel_id: str | None,
        conversation_id: str | None,
        knowledge_base_id: str,
        kb_uuid: str,
        question: str,
        normalized_question: str,
        search_mode: str,
        top_k: int,
        filters: dict | None = None,
        ranking_config: dict | None = None,
        metadata: dict | None = None,
    ) -> SearchQueryRun:
        return SearchQueryRun(
            id=new_id("qry"),
            tenant_slug=tenant_slug,
            user_id=user_id,
            channel_id=channel_id,
            conversation_id=conversation_id,
            knowledge_base_id=knowledge_base_id,
            kb_uuid=kb_uuid,
            question=question,
            normalized_question=normalized_question,
            search_mode=search_mode,
            status="PENDING",
            top_k=top_k,
            filters_json=dict(filters or {}),
            ranking_config_json=dict(ranking_config or {}),
            metadata_json=dict(metadata or {}),
            created_at=utc_now_naive(),
        )


__all__ = ["SearchQueryRunRepository"]
