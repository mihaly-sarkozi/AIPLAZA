from __future__ import annotations

from sqlalchemy import select

from apps.chat.orm.ChatSession import ChatSession
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class ChatSessionRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get(self, session_id: str) -> ChatSession | None:
        with self._session_factory() as session:
            row = session.get(ChatSession, session_id)
            if row is not None:
                session.expunge(row)
            return row

    def create(
        self,
        *,
        tenant_slug: str | None,
        user_id: int | None,
        channel_id: str | None,
        kb_uuid: str | None,
        knowledge_base_id: str | None,
        external_session_id: str | None = None,
        metadata: dict | None = None,
    ) -> ChatSession:
        now = utc_now_naive()
        row = ChatSession(
            id=new_id("conv"),
            tenant_slug=tenant_slug,
            user_id=user_id,
            channel_id=channel_id,
            external_session_id=external_session_id,
            knowledge_base_id=knowledge_base_id,
            kb_uuid=kb_uuid,
            status="active",
            created_at=now,
            updated_at=now,
            last_message_at=now,
            metadata_json=dict(metadata or {}),
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def touch(self, session_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(ChatSession, session_id)
            if row is None:
                return
            row.updated_at = utc_now_naive()
            row.last_message_at = utc_now_naive()
            session.commit()


__all__ = ["ChatSessionRepository"]
