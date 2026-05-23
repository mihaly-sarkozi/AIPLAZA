# backend/apps/chat/service/chat_stream_service.py
# Owns chat streaming orchestration around context, PII guarding and LLM generation.

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Callable

from apps.chat.service.llm_answer_service import LLMAnswerService
from apps.chat.service.pii_chat_guard_service import PiiChatGuardService, PiiDepersonalizationUnavailableError

logger = logging.getLogger(__name__)


class ChatStreamService:
    def __init__(
        self,
        *,
        context_packet_service: Any,
        pii_chat_guard: PiiChatGuardService,
        llm_answer_service: LLMAnswerService,
        build_messages: Callable[..., list[dict[str, str]]],
        fold_text: Callable[[str | None], str],
        context_timeout_sec: int,
        max_answer_chars: int,
    ) -> None:
        self._context_packet_service = context_packet_service
        self._pii_chat_guard = pii_chat_guard
        self._llm_answer_service = llm_answer_service
        self._build_messages = build_messages
        self._fold_text = fold_text
        self._context_timeout_sec = context_timeout_sec
        self._max_answer_chars = max_answer_chars

    async def stream(
        self,
        *,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
    ) -> AsyncIterator[str]:
        try:
            packet = await asyncio.wait_for(
                self._context_packet_service.build(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    kb_uuid=kb_uuid,
                    debug=False,
                ),
                timeout=self._context_timeout_sec,
            )
            context_text = self._context_packet_service.llm_text(packet)
            pii_context = self._pii_chat_guard.prepare_question(
                packet=packet if isinstance(packet, dict) else {},
                kb_uuid=kb_uuid,
                question=question,
                context_text=context_text,
                user_id=user_id,
                source="chat_stream",
                include_history=False,
                fold_text=self._fold_text,
            )
            messages = self._build_messages(
                question=pii_context.encoded_question,
                context_text=pii_context.encoded_context_text,
                pii_prompt_policy=pii_context.prompt_policy,
                brand_voice=str(packet.get("brand_voice") or packet.get("style") or "").strip() if isinstance(packet, dict) else "",
                channel_settings=packet.get("channel_settings") if isinstance(packet, dict) and isinstance(packet.get("channel_settings"), dict) else None,
                safety_constraints=(
                    "Csak a tudástár-contexttel alátámasztott tény állítható. Bizonytalan esetben jelezd röviden, hogy nincs elég adat."
                    if pii_context.encoded_context_text
                    else ""
                ),
                citation_context=(
                    "Elérhető citation source id-k: "
                    + ", ".join(str(item) for item in (packet.get("cited_source_ids") or []) if str(item).strip())
                    if isinstance(packet, dict) and isinstance(packet.get("cited_source_ids"), list) and packet.get("cited_source_ids")
                    else ""
                ),
            )
            answer = await self._llm_answer_service.generate(messages)
            restored_answer = self._pii_chat_guard.restore_answer(str(answer or ""), pii_context)
            yield str(restored_answer.text or "")[: self._max_answer_chars]
        except PiiDepersonalizationUnavailableError:
            raise
        except Exception as e:
            logger.error("Váratlan hiba a chat stream szolgáltatásban: %s", e, exc_info=True)
            yield "⚠️ Nem sikerült választ kapni a modellből."


__all__ = ["ChatStreamService"]
