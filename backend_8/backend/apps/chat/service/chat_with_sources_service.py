# backend/apps/chat/service/chat_with_sources_service.py
# Owns the chat-with-sources orchestration flow.

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from core.kernel.interface.observability import increment_metric

from apps.chat.errors import ChatPermissionDenied
from apps.chat.service.answer_post_processor import AnswerPostProcessor
from apps.chat.service.chat_telemetry_service import ChatTelemetryService
from apps.chat.service.llm_answer_service import LLMAnswerService
from apps.chat.service.pii_chat_guard_service import PiiChatContext, PiiChatGuardService

logger = logging.getLogger(__name__)


@dataclass
class ContextBuildResult:
    packet: dict[str, Any]
    context_text: str
    context_failed: bool
    context_build_ms: float
    direct_payload: dict[str, Any] | None = None


class ChatWithSourcesService:
    def __init__(
        self,
        *,
        build_context_packet: Callable[..., Any],
        llm_context_text_from_packet: Callable[[dict[str, Any]], str],
        pii_chat_guard: PiiChatGuardService,
        llm_answer_service: LLMAnswerService,
        answer_post_processor: AnswerPostProcessor,
        build_messages: Callable[..., list[dict[str, str]]],
        build_prompt_context_payload: Callable[..., dict[str, Any]],
        knowledge_payload: Callable[..., dict[str, Any]],
        should_return_direct_knowledge_answer: Callable[..., bool],
        looks_broad_enumeration_request: Callable[[str], bool],
        policy_violation_error: Callable[[str], Exception],
        fold_text: Callable[[str | None], str],
        kb_service: Callable[[], Any | None] | Any | None,
        context_timeout_sec: int,
        max_answer_chars: int,
        enumeration_policy_detail: str,
        telemetry_service: ChatTelemetryService | None = None,
    ) -> None:
        self._build_context_packet = build_context_packet
        self._llm_context_text_from_packet = llm_context_text_from_packet
        self._pii_chat_guard = pii_chat_guard
        self._llm_answer_service = llm_answer_service
        self._answer_post_processor = answer_post_processor
        self._build_messages = build_messages
        self._build_prompt_context_payload = build_prompt_context_payload
        self._knowledge_payload = knowledge_payload
        self._should_return_direct_knowledge_answer = should_return_direct_knowledge_answer
        self._looks_broad_enumeration_request = looks_broad_enumeration_request
        self._policy_violation_error = policy_violation_error
        self._fold_text = fold_text
        self._kb_service = kb_service
        self._context_timeout_sec = context_timeout_sec
        self._max_answer_chars = max_answer_chars
        self._enumeration_policy_detail = enumeration_policy_detail
        self._telemetry_service = telemetry_service or ChatTelemetryService()

    async def _call_build_context_packet(self, **kwargs: Any) -> dict[str, Any]:
        result = self._build_context_packet(**kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result

    def _current_kb_service(self) -> Any | None:
        if callable(self._kb_service):
            return self._kb_service()
        return self._kb_service

    async def build(
        self,
        *,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        self._enforce_request_policy(question=question, user_role=user_role)
        context_result = await self._build_context(
            question=question,
            user_id=user_id,
            user_role=user_role,
            kb_uuid=kb_uuid,
            tenant=tenant,
            debug=debug,
            started_at=started_at,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
        )
        if context_result.direct_payload is not None:
            return context_result.direct_payload

        packet = context_result.packet
        context_text = context_result.context_text
        context_failed = context_result.context_failed
        pii_context = self._pii_chat_guard.prepare_question(
            packet=packet if isinstance(packet, dict) else {},
            kb_uuid=kb_uuid,
            question=question,
            context_text=context_text,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
            user_id=user_id,
            source="chat_with_sources",
            include_history=True,
            fold_text=self._fold_text,
        )

        answer, llm_ms, encoded_answer_text, restored_pii_spans, prompt_context = await self._answer_with_prompt(
            question=question,
            user_id=user_id,
            packet=packet,
            context_text=context_text,
            context_failed=context_failed,
            pii_context=pii_context,
            kb_uuid=kb_uuid,
            debug=debug,
        )
        self._record_timing(
            packet=packet,
            context_build_ms=context_result.context_build_ms,
            llm_ms=llm_ms,
            started_at=started_at,
            user_role=user_role,
            kb_uuid=kb_uuid,
            context_text=context_text,
            context_failed=context_failed,
            prompt_context=prompt_context,
            encoded_answer_text=encoded_answer_text,
        )
        payload = self._answer_post_processor.build_payload(
            packet=packet,
            answer=str(answer or ""),
            context_text=context_text,
            context_failed=context_failed,
            prompt_context=prompt_context,
            encoded_prompt_context=pii_context.encoded_context_text,
            restored_pii_spans=restored_pii_spans,
            pii_enabled=pii_context.enabled,
            debug=debug,
            kb_uuid=kb_uuid,
        )
        self._reinforce_followup(packet=packet, context_text=context_text, context_failed=context_failed, kb_uuid=kb_uuid)
        return payload

    def _enforce_request_policy(self, *, question: str, user_role: str | None) -> None:
        if str(user_role or "").strip().lower() == "channel" and self._looks_broad_enumeration_request(question):
            increment_metric("channel.chat.rejected.enumeration", 1.0)
            raise self._policy_violation_error(self._enumeration_policy_detail)

    async def _build_context(
        self,
        *,
        question: str,
        user_id: int | None,
        user_role: str | None,
        kb_uuid: str | None,
        tenant: str | None,
        debug: bool,
        started_at: float,
        conversation_history: list[dict[str, str]] | None,
        retrieval_history: list[str] | None,
    ) -> ContextBuildResult:
        try:
            context_started_at = perf_counter()
            packet = await asyncio.wait_for(
                self._call_build_context_packet(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    kb_uuid=kb_uuid,
                    tenant=tenant,
                    debug=debug,
                ),
                timeout=self._context_timeout_sec,
            )
            context_build_ms = round((perf_counter() - context_started_at) * 1000.0, 2)
            synthesized_answer = str(packet.get("answer_text") or "").strip()
            if synthesized_answer and self._should_return_direct_knowledge_answer(packet, question=question):
                packet["_chat_timing_ms"] = {
                    "context_build": context_build_ms,
                    "llm": 0.0,
                    "total": round((perf_counter() - started_at) * 1000.0, 2),
                }
                return ContextBuildResult(
                    packet=packet,
                    context_text="",
                    context_failed=False,
                    context_build_ms=context_build_ms,
                    direct_payload=self._knowledge_payload(
                        packet=packet,
                        debug=debug,
                        question=question,
                        conversation_history=conversation_history,
                        retrieval_history=retrieval_history,
                    ),
                )
            return ContextBuildResult(
                packet=packet,
                context_text=self._llm_context_text_from_packet(packet),
                context_failed=False,
                context_build_ms=context_build_ms,
            )
        except (ChatPermissionDenied, PermissionError):
            raise
        except asyncio.TimeoutError:
            context_build_ms = round((perf_counter() - started_at) * 1000.0, 2)
            logger.warning("chat_with_sources context timeout (%ss).", self._context_timeout_sec, exc_info=True)
            return ContextBuildResult(packet={}, context_text="", context_failed=True, context_build_ms=context_build_ms)
        except Exception as e:
            context_build_ms = round((perf_counter() - started_at) * 1000.0, 2)
            logger.warning("chat_with_sources context hiba: %s", e, exc_info=True)
            return ContextBuildResult(packet={}, context_text="", context_failed=True, context_build_ms=context_build_ms)

    async def _answer_with_prompt(
        self,
        *,
        question: str,
        user_id: int | None,
        packet: dict[str, Any],
        context_text: str,
        context_failed: bool,
        pii_context: PiiChatContext,
        kb_uuid: str | None,
        debug: bool,
    ) -> tuple[str, float, str, list[dict[str, Any]], dict[str, Any]]:
        encoded_answer_text = ""
        restored_pii_spans: list[dict[str, Any]] = []
        if context_failed or not context_text.strip():
            self._record_missing_context_if_needed(packet=packet, question=question, user_id=user_id, kb_uuid=kb_uuid)
            answer = "Nem találtam releváns választ a kiválasztott tudástárban."
            prompt_context = self._prompt_context(
                question=question,
                messages=[],
                packet=packet,
                context_text=context_text,
                pii_context=pii_context,
                encoded_answer_text=encoded_answer_text,
            )
            return answer, 0.0, encoded_answer_text, restored_pii_spans, prompt_context

        messages = self._messages_for_context(packet=packet, context_text=context_text, pii_context=pii_context)
        prompt_context = self._prompt_context(
            question=question,
            messages=messages,
            packet=packet,
            context_text=context_text,
            pii_context=pii_context,
            encoded_answer_text=encoded_answer_text,
        )
        if debug:
            logger.info(
                "chat.raw_inputs_before_pii",
                extra={
                    "kb_uuid": str(packet.get("kb_uuid") or packet.get("corpus_uuid") or kb_uuid or "").strip() or None,
                    "question": pii_context.raw_question_before_pii,
                    "context_text": pii_context.raw_context_before_pii,
                    "conversation_history": pii_context.raw_conversation_history_before_pii,
                    "retrieval_history": pii_context.raw_retrieval_history_before_pii,
                },
            )
        answer, llm_ms = await self._llm_answer_service.generate_with_timing(messages)
        encoded_answer_text = str(answer or "")
        restored_answer = self._pii_chat_guard.restore_answer(str(answer or ""), pii_context)
        return (
            str(restored_answer.text or "")[: self._max_answer_chars],
            llm_ms,
            encoded_answer_text,
            restored_answer.restored_spans,
            prompt_context,
        )

    def _messages_for_context(
        self,
        *,
        packet: dict[str, Any],
        context_text: str,
        pii_context: PiiChatContext,
    ) -> list[dict[str, str]]:
        brand_voice = str(packet.get("brand_voice") or packet.get("style") or "").strip() if isinstance(packet, dict) else ""
        channel_settings = packet.get("channel_settings") if isinstance(packet, dict) and isinstance(packet.get("channel_settings"), dict) else None
        citation_ids = packet.get("cited_source_ids") if isinstance(packet, dict) else None
        citation_context = ""
        if isinstance(citation_ids, list) and citation_ids:
            citation_context = "Elérhető citation source id-k: " + ", ".join(str(item) for item in citation_ids if str(item).strip())
        return self._build_messages(
            question=pii_context.encoded_question,
            context_text=pii_context.encoded_context_text,
            conversation_history=pii_context.encoded_conversation_history,
            retrieval_history=pii_context.encoded_retrieval_history,
            pii_prompt_policy=pii_context.prompt_policy,
            brand_voice=brand_voice,
            channel_settings=channel_settings,
            safety_constraints=(
                "Csak a tudástár-contexttel alátámasztott tény állítható. Bizonytalan esetben jelezd röviden, hogy nincs elég adat."
                if context_text
                else ""
            ),
            citation_context=citation_context,
        )

    def _prompt_context(
        self,
        *,
        question: str,
        messages: list[dict[str, str]],
        packet: dict[str, Any],
        context_text: str,
        pii_context: PiiChatContext,
        encoded_answer_text: str,
    ) -> dict[str, Any]:
        return self._build_prompt_context_payload(
            question=question,
            messages=messages,
            conversation_history=pii_context.encoded_conversation_history,
            retrieval_history=pii_context.encoded_retrieval_history,
            packet=packet or {},
            context_text=context_text,
            encoded_question=pii_context.encoded_question,
            encoded_context_text=pii_context.encoded_context_text,
            pii_prompt_policy=pii_context.prompt_policy,
            pii_applied=pii_context.applied,
            pii_reason=pii_context.reason,
            encoded_answer_text=encoded_answer_text,
            raw_question_before_pii=pii_context.raw_question_before_pii,
            raw_context_before_pii=pii_context.raw_context_before_pii,
            raw_conversation_history_before_pii=pii_context.raw_conversation_history_before_pii,
            raw_retrieval_history_before_pii=pii_context.raw_retrieval_history_before_pii,
        )

    def _record_missing_context_if_needed(
        self,
        *,
        packet: dict[str, Any],
        question: str,
        user_id: int | None,
        kb_uuid: str | None,
    ) -> None:
        self._telemetry_service.record_missing_context_if_needed(
            packet=packet,
            question=question,
            user_id=user_id,
            kb_uuid=kb_uuid,
        )

    def _record_timing(
        self,
        *,
        packet: dict[str, Any],
        context_build_ms: float,
        llm_ms: float,
        started_at: float,
        user_role: str | None,
        kb_uuid: str | None,
        context_text: str,
        context_failed: bool,
        prompt_context: dict[str, Any],
        encoded_answer_text: str,
    ) -> None:
        self._telemetry_service.record_timing(
            packet=packet,
            context_build_ms=context_build_ms,
            llm_ms=llm_ms,
            started_at=started_at,
            user_role=user_role,
            kb_uuid=kb_uuid,
            context_text=context_text,
            context_failed=context_failed,
            prompt_context=prompt_context,
            encoded_answer_text=encoded_answer_text,
        )

    def _reinforce_followup(
        self,
        *,
        packet: dict[str, Any],
        context_text: str,
        context_failed: bool,
        kb_uuid: str | None,
    ) -> None:
        kb_service = self._current_kb_service()
        if not context_text or context_failed or not packet.get("is_followup") or kb_service is None:
            return
        for row in packet.get("top_assertions") or []:
            aid = str(row.get("id") or "")
            kb_uuid_for_row = str(row.get("kb_uuid") or kb_uuid or "")
            if aid.startswith("assertion-") and aid.split("-", 1)[1].isdigit() and kb_uuid_for_row:
                try:
                    kb_service.reinforce_assertion(
                        kb_uuid=kb_uuid_for_row,
                        assertion_id=int(aid.split("-", 1)[1]),
                        event_type="USER_FOLLOWUP",
                    )
                except Exception:
                    pass


__all__ = ["ChatWithSourcesService"]
