from __future__ import annotations

from sqlalchemy import select

from apps.chat.orm.ChatTurn import ChatTurn
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class ChatTurnRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        session_id: str,
        tenant_slug: str | None,
        role: str,
        message_text: str,
        query_run_id: str | None = None,
        answer_mode: str | None = None,
        metadata: dict | None = None,
    ) -> ChatTurn:
        row = ChatTurn(
            id=new_id("turn"),
            session_id=session_id,
            tenant_slug=tenant_slug,
            role=role,
            message_text=message_text,
            query_run_id=query_run_id,
            answer_mode=answer_mode,
            metadata_json=dict(metadata or {}),
            created_at=utc_now_naive(),
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_for_session(self, session_id: str, *, limit: int = 40) -> list[ChatTurn]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(ChatTurn)
                    .where(ChatTurn.session_id == session_id)
                    .order_by(ChatTurn.created_at.asc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows


__all__ = ["ChatTurnRepository"]
