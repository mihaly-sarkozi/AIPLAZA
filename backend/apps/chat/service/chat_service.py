# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
import logging
import threading
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Optional

from core.kernel.interface.observability import increment_metric, observe_metric

from apps.chat.errors import ChatPolicyViolation
from apps.chat.service.answer_download_service import AnswerDownloadService, PermissionSubject
from apps.chat.service.answer_post_processor import AnswerPostProcessor
from apps.chat.service.chat_debug_payload_builder import ChatDebugPayloadBuilder
from apps.chat.service.llm_answer_service import LLMAnswerService
from apps.chat.service.pii_chat_guard_service import PiiChatGuardService, PiiDepersonalizationUnavailableError
from apps.chat.service.pii_depersonalization import PiiDepersonalizationService
from apps.chat.service.chat_text_utils import (
    dedupe_keep_order,
    estimate_prompt_chars,
    fold_text,
)
from apps.chat.service.chat_service_factory import build_chat_service_runtime
from apps.chat.service.chat_context_packet_service import ChatContextPacketService
from apps.chat.service.chat_query_enrichment_service import ChatQueryEnrichmentService
from apps.chat.service.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class ChatPolicyViolationError(ChatPolicyViolation):
    """Raised when a chat request violates policy rules."""


class ChatService:
    _budget_lock = threading.Lock()
    _budget_state: dict[tuple[str, str], dict[str, int]] = {}
    _INSUFFICIENT_CONTEXT_ANSWER = "Nincs elegendő információ a válaszhoz a kiválasztott tudástár alapján."
    _MAX_CONVERSATION_HISTORY_MESSAGES = 20
    _MAX_CONVERSATION_HISTORY_CHARS = 2200
    _MAX_CONTEXT_BLOCKS = 1
    _MAX_PRIMARY_ASSERTIONS = 4
    _MAX_SUPPORTING_ASSERTIONS = 3
    _MAX_EVIDENCE_LINES = 3
    _MAX_CONTEXT_CHUNKS = 2
    _MAX_CONTEXT_TEXT_CHARS = 1400
    _MAX_CONTEXT_BLOCK_SNIPPET_CHARS = 520
    _MAX_RETRIEVAL_HISTORY_ITEMS = 4
    _MAX_RETRIEVAL_HISTORY_CHARS = 1000
    _MULTI_KB_PACKET_SCORE_THRESHOLD = 0.45
    _MULTI_KB_BLOCK_SCORE_THRESHOLD = 0.35
    _MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO = 0.8
    _ENUMERATION_POLICY_DETAIL = (
        "A kérés túl általános listázást céloz. Pontosítsd a kérdést konkrét entitással, időszakkal vagy témával."
    )

    @staticmethod
    def _openai_client(**kwargs: Any):
        return LLMAnswerService.openai_client(**kwargs)

    def _chat_completion_kwargs(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return self._llm_answer_service.chat_completion_kwargs(messages)

    @staticmethod
    def _coerce_response_text(value: Any) -> str:
        return LLMAnswerService.coerce_response_text(value)

    def _extract_response_text(self, response: Any) -> str:
        return self._llm_answer_service.extract_response_text(response)

    @staticmethod
    def _policy_violation_error(*args: Any, **kwargs: Any) -> ChatPolicyViolationError:
        return ChatPolicyViolationError(*args, **kwargs)

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        chat_model: Optional[Any] = None,
        chat_model_name: str | None = None,
        kb_service: Any = None,
        retrieval_service: Any = None,
        query_parser: Any = None,
        context_builder: Any = None,
        channel_access_service: Any = None,
        pii_depersonalization_service: PiiDepersonalizationService | None = None,
        audit_service: Any = None,
        chat_session_service: Any = None,
    ):
        build_chat_service_runtime(
            self,
            chat_model=chat_model,
            chat_model_name=chat_model_name,
            kb_service=kb_service,
            retrieval_service=retrieval_service,
            query_parser=query_parser,
            context_builder=context_builder,
            channel_access_service=channel_access_service,
            pii_depersonalization_service=pii_depersonalization_service,
            audit_service=audit_service,
            chat_session_service=chat_session_service,
        )

    @staticmethod
    def estimate_prompt_chars(
        *,
        question: str,
        conversation_history: list[dict[str, str]] | None,
        retrieval_history: list[str] | None,
    ) -> int:
        return estimate_prompt_chars(
            question=question,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
        )

    # Ez a metódus a(z) capture_retrieval_feedback logikáját valósítja meg.
    def capture_retrieval_feedback(
        self,
        trace_id: str,
        helpful: bool | None = None,
        context_useful: bool | None = None,
        wrong_entity_resolution: bool = False,
        wrong_time_slice: bool = False,
        note: str | None = None,
    ) -> dict:
        if self.retrieval_service is None or not hasattr(self.retrieval_service, "capture_feedback"):
            return {"status": "skipped", "reason": "feedback_service_not_available"}
        return self.retrieval_service.capture_feedback(
            trace_id=trace_id,
            helpful=helpful,
            context_useful=context_useful,
            wrong_entity_resolution=wrong_entity_resolution,
            wrong_time_slice=wrong_time_slice,
            note=note,
        )

    def download_answer_source(
        self,
        *,
        query_run_id: str,
        source_id: str,
        user_id: int | None = None,
        user_role: str | None = None,
    ) -> dict | None:
        return self._answer_downloads.download_answer_source(
            query_run_id=query_run_id,
            source_id=source_id,
            user_id=user_id,
            user_role=user_role,
        )

    def download_answer_context(
        self,
        *,
        query_run_id: str,
        user_id: int | None = None,
        user_role: str | None = None,
    ) -> dict | None:
        return self._answer_downloads.download_answer_context(
            query_run_id=query_run_id,
            user_id=user_id,
            user_role=user_role,
        )

    # Ez a metódus a(z) utcnow_naive logikáját valósítja meg.
    @staticmethod
    def _utcnow_naive() -> datetime:
        from core.kernel.runtime.clock import utc_now_naive

        return utc_now_naive()

    # Ez a metódus a(z) dedupe_keep_order logikáját valósítja meg.
    @staticmethod
    def _dedupe_keep_order(values: list[str]) -> list[str]:
        return dedupe_keep_order(values)

    @staticmethod
    def _fold_text(value: str | None) -> str:
        return fold_text(value)

    # Ez a metódus a(z) sanitize_debug_text logikáját valósítja meg.
    @staticmethod
    def _sanitize_debug_text(value: Any) -> str:
        return ChatDebugPayloadBuilder.sanitize_text(value)

    # Ez a metódus a(z) sanitize_debug_value logikáját valósítja meg.
    @classmethod
    def _sanitize_debug_value(cls, value: Any) -> Any:
        return ChatDebugPayloadBuilder.sanitize_value(value)

    def _conversation_history_context(self, conversation_history: list[dict[str, str]] | None) -> str:
        return self._prompt_builder.conversation_history_context(conversation_history)

    def _retrieval_history_context(self, retrieval_history: list[str] | None) -> str:
        return self._prompt_builder.retrieval_history_context(retrieval_history)

    # Ez a metódus normalizálja a(z) place surface logikáját.
    @classmethod
    def _normalize_place_surface(cls, value: str) -> str:
        return ChatQueryEnrichmentService.normalize_place_surface(value)

    @classmethod
    def _normalize_entity_surface(cls, value: str) -> str:
        return ChatQueryEnrichmentService.normalize_entity_surface(value)

    @classmethod
    def _encode_question_using_context_mappings(
        cls,
        *,
        question: str,
        context_mappings: list[dict[str, Any]] | None,
    ) -> str:
        return PiiChatGuardService.encode_question_using_context_mappings(
            question=question,
            context_mappings=context_mappings,
            fold_text=cls._fold_text,
        )

    # Ez a metódus a(z) extract_entity_candidates logikáját valósítja meg.
    @classmethod
    def _extract_entity_candidates(cls, question: str) -> list[str]:
        return ChatQueryEnrichmentService.extract_entity_candidates(question)

    @classmethod
    def _strong_entity_candidates(cls, query_profile: dict[str, Any]) -> list[str]:
        return ChatQueryEnrichmentService.strong_entity_candidates(query_profile)

    @classmethod
    def _text_matches_strong_entity(cls, text: str, strong_entities: list[str]) -> bool:
        return ChatQueryEnrichmentService.text_matches_strong_entity(text, strong_entities)

    # Ez a metódus a(z) extract_place_candidates logikáját valósítja meg.
    @classmethod
    def _extract_place_candidates(cls, question: str) -> list[str]:
        return ChatQueryEnrichmentService.extract_place_candidates(question)

    # Ez a metódus a(z) extract_time_hints logikáját valósítja meg.
    @classmethod
    def _extract_time_hints(cls, question: str) -> tuple[list[str], dict[str, datetime | None]]:
        return ChatQueryEnrichmentService.extract_time_hints(question)

    # Ez a metódus a(z) derive_intent logikáját valósítja meg.
    @classmethod
    def _derive_intent(cls, question: str, parsed: dict) -> str:
        return ChatQueryEnrichmentService.derive_intent(question, parsed)

    @classmethod
    def _looks_broad_enumeration_request(cls, question: str) -> bool:
        return ChatQueryEnrichmentService.looks_broad_enumeration_request(question)

    # Ez a metódus felépíti a(z) hint terms logikáját.
    @classmethod
    def _build_hint_terms(cls, question: str, parsed: dict) -> list[str]:
        return ChatQueryEnrichmentService.build_hint_terms(question, parsed)

    # Ez a metódus a(z) enrich_parsed_query logikáját valósítja meg.
    @classmethod
    def _enrich_parsed_query(cls, question: str, parsed: dict) -> dict:
        return ChatQueryEnrichmentService.enrich(question, parsed)

    # Ez a metódus a(z) is_followup logikáját valósítja meg.
    def _is_followup(self, user_id: int | None, query_focus: dict) -> bool:
        return self._query_enrichment_service.is_followup(user_id, query_focus)

    async def _build_context_packet(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
        conversation_history: list[dict[str, str]] | None = None,
        channel_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict:
        return await self._context_packet_service.build(
            question=question,
            user_id=user_id,
            user_role=user_role,
            kb_uuid=kb_uuid,
            tenant=tenant,
            debug=debug,
            conversation_history=conversation_history,
            channel_id=channel_id,
            conversation_id=conversation_id,
        )

    async def _build_single_kb_context_packet(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        parsed: dict,
        kb_uuid: str,
        debug: bool,
        tenant: str | None = None,
    ) -> dict:
        return await self._context_packet_service.build_single_kb(
            question=question,
            user_id=user_id,
            user_role=user_role,
            parsed=parsed,
            kb_uuid=kb_uuid,
            debug=debug,
            tenant=tenant,
        )

    async def _build_multi_kb_context_packet(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        permission_subject: PermissionSubject | None,
        parsed: dict,
        debug: bool,
    ) -> dict:
        return await self._context_packet_service.build_multi_kb(
            question=question,
            user_id=user_id,
            user_role=user_role,
            permission_subject=permission_subject,
            parsed=parsed,
            debug=debug,
        )

    @staticmethod
    def _packet_score(packet: dict) -> float:
        return ChatContextPacketService.packet_score(packet)

    @staticmethod
    def _packet_retrieval_confidence(packet: dict[str, Any]) -> float:
        return ChatContextPacketService.packet_retrieval_confidence(packet)

    def _packet_has_strong_context_blocks(
        self,
        packet: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> bool:
        return self._context_packet_service.packet_has_strong_context_blocks(packet, strong_entities=strong_entities)

    def _packet_has_entity_matching_fallback_rows(
        self,
        packet: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> bool:
        return self._context_packet_service.packet_has_entity_matching_fallback_rows(
            packet,
            strong_entities=strong_entities,
        )

    def _candidate_block_score(
        self,
        row: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> float:
        return self._context_packet_service.candidate_block_score(row, strong_entities=strong_entities)

    def _dynamic_multi_kb_block_floor(
        self,
        packets: list[dict[str, Any]],
        *,
        strong_entities: list[str],
    ) -> float:
        return self._context_packet_service.dynamic_multi_kb_block_floor(
            packets,
            strong_entities=strong_entities,
        )

    @staticmethod
    def _stamp_packet_kb(packet: dict, kb_uuid: str, kb_name: str) -> None:
        ChatContextPacketService.stamp_packet_kb(packet, kb_uuid, kb_name)

    def _merge_context_packets(
        self,
        packets: list[dict],
        *,
        kb_names: dict[str, str],
        parsed: dict,
        no_ready_index_build: bool = False,
        multi_kb_diagnostics: dict[str, Any] | None = None,
    ) -> dict:
        return self._context_packet_service.merge_context_packets(
            packets,
            kb_names=kb_names,
            parsed=parsed,
            no_ready_index_build=no_ready_index_build,
            multi_kb_diagnostics=multi_kb_diagnostics,
        )

    async def _safe_context_text(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
    ) -> tuple[str, bool]:
        return await self._context_packet_service.safe_context_text(
            question=question,
            user_id=user_id,
            user_role=user_role,
            kb_uuid=kb_uuid,
            tenant=tenant,
            debug=debug,
        )

    def _context_text_from_packet(self, packet: dict) -> str:
        return self._context_packet_service.context_text(packet)

    def _llm_context_text_from_packet(self, packet: dict) -> str:
        return self._context_packet_service.llm_text(packet)

    def _build_sources_from_packet(self, packet: dict) -> list[dict]:
        return self._answer_post_processor.build_sources_from_packet(packet)

    @staticmethod
    def _is_knowledge_answer(packet: dict) -> bool:
        return AnswerPostProcessor.is_knowledge_answer(packet)

    @staticmethod
    def _chat_evidence(packet: dict) -> list[dict]:
        return AnswerPostProcessor.chat_evidence(packet)

    @staticmethod
    def _chat_confidence(packet: dict) -> float:
        return AnswerPostProcessor.chat_confidence(packet)

    @staticmethod
    def _looks_hungarian_question(question: str) -> bool:
        return AnswerPostProcessor.looks_hungarian_question(question)

    @staticmethod
    def _looks_english_template_answer(answer: str) -> bool:
        return AnswerPostProcessor.looks_english_template_answer(answer)

    @classmethod
    def _should_return_direct_knowledge_answer(cls, packet: dict, *, question: str = "") -> bool:
        return AnswerPostProcessor.should_return_direct_knowledge_answer(packet, question=question)

    def _knowledge_payload(
        self,
        *,
        packet: dict,
        debug: bool,
        question: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> dict:
        return self._answer_post_processor.build_knowledge_payload(
            packet=packet,
            debug=debug,
            question=question,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
        )

    # Ez a metódus felépíti a(z) debug payload logikáját.
    def _build_debug_payload(self, packet: dict, context_text: str, sources: list[dict]) -> dict:
        return self._debug_payload_builder.build(packet, context_text, sources)

    def _kb_pii_settings(self, *, packet: dict[str, Any], kb_uuid: str | None) -> tuple[bool, str, str]:
        return PiiChatGuardService.kb_pii_settings(packet=packet, kb_uuid=kb_uuid)

    @staticmethod
    def _pii_prompt_policy() -> str:
        return PiiChatGuardService.prompt_policy()

    def _normalize_pii_policy_refusal(self, text: str) -> str:
        return self._pii_chat_guard.normalize_policy_refusal(text)

    def _audit_pii_encode(
        self,
        *,
        user_id: int | None,
        corpus_uuid: str | None,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._pii_chat_guard.audit_encode(
            user_id=user_id,
            corpus_uuid=corpus_uuid,
            outcome=outcome,
            details=details,
        )

    @staticmethod
    def _emit_pii_encode_metrics(
        *,
        sensitivity: str,
        outcome: str,
        duration_ms: float,
        token_count: int,
    ) -> None:
        PiiChatGuardService.emit_encode_metrics(
            sensitivity=sensitivity,
            outcome=outcome,
            duration_ms=duration_ms,
            token_count=token_count,
        )

    def _raise_pii_encode_unavailable(
        self,
        *,
        kb_uuid: str | None,
        corpus_uuid: str | None,
        user_id: int | None,
        source: str,
        sensitivity: str = "medium",
        duration_ms: float = 0.0,
    ) -> None:
        self._pii_chat_guard.raise_encode_unavailable(
            kb_uuid=kb_uuid,
            corpus_uuid=corpus_uuid,
            user_id=user_id,
            source=source,
            sensitivity=sensitivity,
            duration_ms=duration_ms,
        )

    # Ez a metódus felépíti a(z) messages logikáját.
    @staticmethod
    def _build_messages(
        question: str,
        context_text: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
        pii_prompt_policy: str | None = None,
        brand_voice: str | None = None,
        channel_settings: dict[str, Any] | None = None,
        safety_constraints: str | None = None,
        citation_context: str | None = None,
    ) -> list[dict[str, str]]:
        builder = PromptBuilder(
            max_conversation_history_messages=ChatService._MAX_CONVERSATION_HISTORY_MESSAGES,
            max_conversation_history_chars=ChatService._MAX_CONVERSATION_HISTORY_CHARS,
            max_retrieval_history_items=ChatService._MAX_RETRIEVAL_HISTORY_ITEMS,
            max_retrieval_history_chars=ChatService._MAX_RETRIEVAL_HISTORY_CHARS,
            multi_kb_packet_score_threshold=ChatService._MULTI_KB_PACKET_SCORE_THRESHOLD,
            multi_kb_block_score_threshold=ChatService._MULTI_KB_BLOCK_SCORE_THRESHOLD,
            multi_kb_block_relative_floor_ratio=ChatService._MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO,
        )
        return builder.build_messages(
            question=question,
            context_text=context_text,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
            pii_prompt_policy=pii_prompt_policy,
            brand_voice=brand_voice,
            channel_settings=channel_settings,
            safety_constraints=safety_constraints,
            citation_context=citation_context,
        )

    def _build_prompt_context_payload(
        self,
        *,
        question: str,
        messages: list[dict[str, str]] | None,
        conversation_history: list[dict[str, str]] | None,
        retrieval_history: list[str] | None,
        packet: dict[str, Any],
        context_text: str,
        encoded_question: str | None = None,
        encoded_context_text: str | None = None,
        pii_prompt_policy: str | None = None,
        pii_applied: bool | None = None,
        pii_reason: str | None = None,
        encoded_answer_text: str | None = None,
        raw_question_before_pii: str | None = None,
        raw_context_before_pii: str | None = None,
        raw_conversation_history_before_pii: list[dict[str, str]] | None = None,
        raw_retrieval_history_before_pii: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._prompt_builder.build_prompt_context_payload(
            question=question,
            messages=messages,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
            packet=packet,
            context_text=context_text,
            encoded_question=encoded_question,
            encoded_context_text=encoded_context_text,
            pii_prompt_policy=pii_prompt_policy,
            pii_applied=pii_applied,
            pii_reason=pii_reason,
            encoded_answer_text=encoded_answer_text,
            raw_question_before_pii=raw_question_before_pii,
            raw_context_before_pii=raw_context_before_pii,
            raw_conversation_history_before_pii=raw_conversation_history_before_pii,
            raw_retrieval_history_before_pii=raw_retrieval_history_before_pii,
        )

    # Ez a metódus a(z) insufficient_context_answer logikáját valósítja meg.
    @classmethod
    def _insufficient_context_answer(cls) -> str:
        return cls._INSUFFICIENT_CONTEXT_ANSWER

    async def chat(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> str:
        """Chat üzenet küldése OpenAI API-nak (egyszeri válasz)."""
        try:
            context_text, context_failed = await self._safe_context_text(
                question=question,
                user_id=user_id,
                user_role=user_role,
                kb_uuid=kb_uuid,
                debug=debug,
            )
            if context_failed or not context_text.strip():
                return ""
            messages = self._build_messages(
                question=question,
                context_text="" if context_failed else context_text,
                conversation_history=conversation_history,
                retrieval_history=retrieval_history,
            )
            answer = await self._llm_answer_service.generate(messages)
            answer = self._pii_chat_guard.normalize_policy_refusal(answer)
            if debug and context_text and not context_failed:
                return f"{answer}\n\n[debug-context]\n{self._debug_payload_builder.sanitize_text(context_text)}"
            return str(answer or "")[: self._chat_max_answer_chars]
        except Exception as e:
            logger.error(f"Váratlan hiba a chat szolgáltatásban: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."

    async def chat_with_sources(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
        conversation_id: str | None = None,
        channel_id: str | None = None,
        channel_metadata: dict[str, Any] | None = None,
        base_prompt_id: str | None = None,
    ) -> dict:
        """Chat válasz forráslistával együtt."""
        return await self._chat_with_sources_service.build(
            question=question,
            user_id=user_id,
            user_role=user_role,
            kb_uuid=kb_uuid,
            tenant=tenant,
            debug=debug,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
            conversation_id=conversation_id,
            channel_id=channel_id,
            channel_metadata=channel_metadata,
            base_prompt_id=base_prompt_id,
        )

    async def chat_stream(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
    ) -> AsyncIterator[str]:
        """Streamelt chat válasz: tokenenként yield-eli a tartalmat."""
        async for chunk in self._chat_stream_service.stream(
            question=question,
            user_id=user_id,
            user_role=user_role,
            kb_uuid=kb_uuid,
        ):
            yield chunk


__all__ = ["ChatPolicyViolationError", "ChatService", "PiiDepersonalizationUnavailableError"]
