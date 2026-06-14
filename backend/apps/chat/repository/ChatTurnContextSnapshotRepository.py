from __future__ import annotations

from apps.chat.orm.ChatTurnContextSnapshot import ChatTurnContextSnapshot
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class ChatTurnContextSnapshotRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        turn_id: str,
        session_id: str,
        query_run_id: str | None,
        conversation_context: dict | None,
        search_context: dict | None,
        prompt_context_text: str | None,
        citations: list | None,
        sources: list | None,
        metadata: dict | None = None,
    ) -> ChatTurnContextSnapshot:
        row = ChatTurnContextSnapshot(
            id=new_id("ctxsnap"),
            turn_id=turn_id,
            session_id=session_id,
            query_run_id=query_run_id,
            conversation_context_json=dict(conversation_context or {}),
            search_context_json=dict(search_context or {}),
            prompt_context_text=prompt_context_text,
            citations_json=list(citations or []),
            sources_json=list(sources or []),
            metadata_json=dict(metadata or {}),
            created_at=utc_now_naive(),
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def get_by_query_run(self, query_run_id: str) -> ChatTurnContextSnapshot | None:
        from sqlalchemy import select

        with self._session_factory() as session:
            row = (
                session.execute(
                    select(ChatTurnContextSnapshot)
                    .where(ChatTurnContextSnapshot.query_run_id == query_run_id)
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row


__all__ = ["ChatTurnContextSnapshotRepository"]
