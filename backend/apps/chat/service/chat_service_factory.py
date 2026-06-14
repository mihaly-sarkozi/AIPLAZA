from __future__ import annotations

from typing import Any

from core.kernel.config.config_loader import settings
from apps.chat.service.answer_grounding_validator import AnswerGroundingValidator
from apps.chat.service.answer_download_service import AnswerDownloadService
from apps.chat.service.answer_post_processor import AnswerPostProcessor
from apps.chat.service.chat_context_packet_service import ChatContextPacketService
from apps.chat.service.chat_debug_payload_builder import ChatDebugPayloadBuilder
from apps.chat.service.chat_query_enrichment_service import ChatQueryEnrichmentService
from apps.chat.service.chat_stream_service import ChatStreamService
from apps.chat.service.chat_with_sources_service import ChatWithSourcesService
from apps.chat.service.llm_answer_service import LLMAnswerService
from apps.chat.service.llm_budget import LlmBudgetManager
from apps.chat.service.pii_chat_guard_service import PiiChatGuardService
from apps.chat.service.prompt_builder import PromptBuilder
from apps.chat.service.retrieval_context_builder import RetrievalContextBuilder
from apps.chat.service.chat_text_utils import dedupe_keep_order


def build_chat_service_runtime(
    owner: Any,
    *,
    chat_model: Any = None,
    chat_model_name: str | None = None,
    kb_service: Any = None,
    retrieval_service: Any = None,
    query_parser: Any = None,
    context_builder: Any = None,
    channel_access_service: Any = None,
    pii_depersonalization_service: Any = None,
    audit_service: Any = None,
    chat_session_service: Any = None,
) -> None:
    _wire_external_dependencies(
        owner,
        kb_service=kb_service,
        retrieval_service=retrieval_service,
        query_parser=query_parser,
        context_builder=context_builder,
        channel_access_service=channel_access_service,
        pii_depersonalization_service=pii_depersonalization_service,
        audit_service=audit_service,
        chat_session_service=chat_session_service,
    )
    _wire_llm(owner, chat_model=chat_model, chat_model_name=chat_model_name)
    _wire_context_services(owner)
    _wire_answer_services(owner)


def _wire_external_dependencies(owner: Any, **dependencies: Any) -> None:
    for key, value in dependencies.items():
        setattr(owner, key, value)


def _wire_llm(owner: Any, *, chat_model: Any, chat_model_name: str | None) -> None:
    owner._llm_answer_service = LLMAnswerService.from_settings(
        client=chat_model,
        chat_model_name=chat_model_name,
        client_factory=owner._openai_client,
    )
    owner.client = owner._llm_answer_service.client
    owner.chat_model_name = owner._llm_answer_service.chat_model_name
    owner._chat_completion_timeout_sec = owner._llm_answer_service.completion_timeout_sec
    owner._chat_context_timeout_sec = max(5, int(getattr(settings, "chat_context_timeout_sec", 20) or 20))
    owner._chat_max_tokens = owner._llm_answer_service.chat_max_tokens
    owner._chat_temperature = owner._llm_answer_service.chat_temperature
    owner._chat_max_answer_chars = max(120, int(getattr(settings, "chat_max_answer_chars", 2400) or 2400))


def _wire_context_services(owner: Any) -> None:
    owner._query_enrichment_service = ChatQueryEnrichmentService()
    owner._pii_chat_guard = PiiChatGuardService(
        pii_depersonalization_service=lambda: owner.pii_depersonalization_service,
        audit_service=lambda: owner.audit_service,
        insufficient_context_answer=owner._insufficient_context_answer,
    )
    owner._context_packet_service = ChatContextPacketService(
        query_enrichment_service=owner._query_enrichment_service,
        max_context_blocks=owner._MAX_CONTEXT_BLOCKS,
        max_primary_assertions=owner._MAX_PRIMARY_ASSERTIONS,
        max_supporting_assertions=owner._MAX_SUPPORTING_ASSERTIONS,
        max_evidence_lines=owner._MAX_EVIDENCE_LINES,
        max_context_chunks=owner._MAX_CONTEXT_CHUNKS,
        max_context_text_chars=owner._MAX_CONTEXT_TEXT_CHARS,
        max_context_block_snippet_chars=owner._MAX_CONTEXT_BLOCK_SNIPPET_CHARS,
        multi_kb_packet_score_threshold=owner._MULTI_KB_PACKET_SCORE_THRESHOLD,
        multi_kb_block_score_threshold=owner._MULTI_KB_BLOCK_SCORE_THRESHOLD,
        multi_kb_block_relative_floor_ratio=owner._MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO,
        context_timeout_sec=owner._chat_context_timeout_sec,
    )
    owner._prompt_builder = PromptBuilder(
        max_conversation_history_messages=owner._MAX_CONVERSATION_HISTORY_MESSAGES,
        max_conversation_history_chars=owner._MAX_CONVERSATION_HISTORY_CHARS,
        max_retrieval_history_items=owner._MAX_RETRIEVAL_HISTORY_ITEMS,
        max_retrieval_history_chars=owner._MAX_RETRIEVAL_HISTORY_CHARS,
        multi_kb_packet_score_threshold=owner._MULTI_KB_PACKET_SCORE_THRESHOLD,
        multi_kb_block_score_threshold=owner._MULTI_KB_BLOCK_SCORE_THRESHOLD,
        multi_kb_block_relative_floor_ratio=owner._MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO,
    )
    owner._retrieval_context_builder = RetrievalContextBuilder(
        kb_service=owner.kb_service,
        retrieval_service=owner.retrieval_service,
        query_parser=owner.query_parser,
        context_builder=owner.context_builder,
        enrich_parsed_query=owner._query_enrichment_service.enrich,
        is_followup=owner._query_enrichment_service.is_followup,
        llm_context_text_from_packet=owner._context_packet_service.llm_text,
        stamp_packet_kb=owner._context_packet_service.stamp_packet_kb,
        merge_context_packets=owner._context_packet_service.merge_context_packets,
    )
    owner._context_packet_service.set_retrieval_context_builder(owner._retrieval_context_builder)


def _wire_answer_services(owner: Any) -> None:
    owner._llm_budget_manager = LlmBudgetManager.from_settings(
        chat_max_tokens=owner._chat_max_tokens,
        lock=owner._budget_lock,
        state=owner._budget_state,
    )
    owner._debug_payload_builder = ChatDebugPayloadBuilder(dedupe_keep_order=dedupe_keep_order)
    owner._answer_post_processor = AnswerPostProcessor(
        sanitize_debug_text=owner._debug_payload_builder.sanitize_text,
        context_text_from_packet=owner._context_packet_service.context_text,
        build_messages=owner._build_messages,
        build_prompt_context_payload=owner._build_prompt_context_payload,
        build_debug_payload=owner._debug_payload_builder.build,
        kb_pii_settings=owner._pii_chat_guard.kb_pii_settings,
        pii_depersonalization_service=lambda: owner.pii_depersonalization_service,
        max_answer_chars=owner._chat_max_answer_chars,
        insufficient_context_answer=owner._insufficient_context_answer,
    )
    owner._chat_stream_service = ChatStreamService(
        context_packet_service=owner._context_packet_service,
        pii_chat_guard=owner._pii_chat_guard,
        llm_answer_service=owner._llm_answer_service,
        build_messages=owner._build_messages,
        fold_text=owner._fold_text,
        context_timeout_sec=owner._chat_context_timeout_sec,
        max_answer_chars=owner._chat_max_answer_chars,
    )
    owner._chat_with_sources_service = ChatWithSourcesService(
        build_context_packet=lambda **kwargs: owner._build_context_packet(**kwargs),
        llm_context_text_from_packet=lambda packet: owner._llm_context_text_from_packet(packet),
        pii_chat_guard=owner._pii_chat_guard,
        llm_answer_service=owner._llm_answer_service,
        answer_post_processor=owner._answer_post_processor,
        build_messages=lambda **kwargs: owner._build_messages(**kwargs),
        build_prompt_context_payload=lambda **kwargs: owner._build_prompt_context_payload(**kwargs),
        knowledge_payload=lambda **kwargs: owner._knowledge_payload(**kwargs),
        should_return_direct_knowledge_answer=lambda *args, **kwargs: owner._should_return_direct_knowledge_answer(*args, **kwargs),
        looks_broad_enumeration_request=lambda question: owner._looks_broad_enumeration_request(question),
        policy_violation_error=owner._policy_violation_error,
        fold_text=owner._fold_text,
        kb_service=lambda: owner.kb_service,
        context_timeout_sec=owner._chat_context_timeout_sec,
        max_answer_chars=owner._chat_max_answer_chars,
        enumeration_policy_detail=owner._ENUMERATION_POLICY_DETAIL,
        grounding_validator=AnswerGroundingValidator(),
        chat_session_service=lambda: getattr(owner, "chat_session_service", None),
    )
    owner._answer_downloads = AnswerDownloadService(
        kb_service=owner.kb_service,
        retrieval_service=owner.retrieval_service,
    )


__all__ = ["build_chat_service_runtime"]
