from __future__ import annotations

import logging
from typing import Any

from apps.chat.repository.ChatSessionRepository import ChatSessionRepository
from apps.chat.repository.ChatTurnContextSnapshotRepository import ChatTurnContextSnapshotRepository
from apps.chat.repository.ChatTurnRepository import ChatTurnRepository
from core.kernel.interface.observability import log_structured_event


class ChatSessionService:
    def __init__(
        self,
        *,
        session_repository: ChatSessionRepository,
        turn_repository: ChatTurnRepository,
        snapshot_repository: ChatTurnContextSnapshotRepository,
    ) -> None:
        self._sessions = session_repository
        self._turns = turn_repository
        self._snapshots = snapshot_repository

    def resolve_or_create_session(
        self,
        *,
        conversation_id: str | None,
        tenant_slug: str | None,
        user_id: int | None,
        kb_uuid: str | None,
        channel_id: str | None = None,
        external_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        if conversation_id:
            session = self._sessions.get(conversation_id)
            if session is not None:
                history = self._history_from_turns(conversation_id)
                return conversation_id, history

        session = self._sessions.create(
            tenant_slug=tenant_slug,
            user_id=user_id,
            channel_id=channel_id,
            kb_uuid=kb_uuid,
            knowledge_base_id=kb_uuid,
            external_session_id=external_session_id,
            metadata=metadata,
        )
        log_structured_event("apps.chat", "CHAT_SESSION_CREATED", level=logging.INFO, session_id=session.id)
        return session.id, []

    def store_user_message(
        self,
        *,
        session_id: str,
        tenant_slug: str | None,
        message_text: str,
    ) -> str:
        turn = self._turns.create(
            session_id=session_id,
            tenant_slug=tenant_slug,
            role="user",
            message_text=message_text,
        )
        self._sessions.touch(session_id)
        log_structured_event(
            "apps.chat",
            "CHAT_USER_MESSAGE_STORED",
            level=logging.INFO,
            session_id=session_id,
            turn_id=turn.id,
        )
        return turn.id

    def store_assistant_turn(
        self,
        *,
        session_id: str,
        tenant_slug: str | None,
        answer: str,
        query_run_id: str | None,
        answer_mode: str | None,
        packet: dict[str, Any] | None,
        conversation_history: list[dict[str, str]] | None,
        prompt_context: dict[str, Any] | None,
        sources: list[dict[str, Any]] | None,
        citations: list | None = None,
        context_blocks: list | None = None,
        matched_chunks: list | None = None,
    ) -> str:
        turn = self._turns.create(
            session_id=session_id,
            tenant_slug=tenant_slug,
            role="assistant",
            message_text=answer,
            query_run_id=query_run_id,
            answer_mode=answer_mode,
        )
        if packet is not None:
            resolved_sources = sources if sources is not None else (packet.get("sources") or [])
            resolved_citations = citations if citations is not None else (packet.get("citations") or [])
            resolved_context_blocks = context_blocks if context_blocks is not None else (packet.get("context_blocks") or [])
            resolved_matched_chunks = matched_chunks if matched_chunks is not None else (packet.get("matched_chunks") or [])
            self._snapshots.create(
                turn_id=turn.id,
                session_id=session_id,
                query_run_id=query_run_id,
                conversation_context={"history": conversation_history or []},
                search_context={
                    "context_blocks": resolved_context_blocks,
                    "matched_chunks": resolved_matched_chunks,
                    "query_profile": packet.get("query_profile") or {},
                },
                prompt_context_text=str(packet.get("prompt_context") or ""),
                citations=resolved_citations,
                sources=resolved_sources,
                metadata={"prompt_context": prompt_context or {}},
            )
        self._sessions.touch(session_id)
        log_structured_event(
            "apps.chat",
            "CHAT_RESPONSE_STORED",
            level=logging.INFO,
            session_id=session_id,
            turn_id=turn.id,
        )
        return turn.id

    def get_session_payload(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        turns = self._turns.list_for_session(session_id)
        return {
            "conversation_id": session.id,
            "kb_uuid": session.kb_uuid,
            "channel_id": session.channel_id,
            "status": session.status,
            "turns": [
                {
                    "turn_id": turn.id,
                    "role": turn.role,
                    "message_text": turn.message_text,
                    "query_run_id": turn.query_run_id,
                    "answer_mode": turn.answer_mode,
                    "created_at": turn.created_at.isoformat() if turn.created_at else None,
                }
                for turn in turns
            ],
        }

    def _history_from_turns(self, session_id: str) -> list[dict[str, str]]:
        turns = self._turns.list_for_session(session_id)
        history: list[dict[str, str]] = []
        for turn in turns:
            role = str(turn.role or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            history.append({"role": role, "content": str(turn.message_text or "")})
        return history


__all__ = ["ChatSessionService"]
