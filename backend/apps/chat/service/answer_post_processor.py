# backend/apps/chat/service/answer_post_processor.py
# Owns answer payload normalization, source list building and knowledge-answer decisions.

from __future__ import annotations

import logging
from typing import Any, Callable

from apps.chat.service.answer_source_builder import AnswerSourceBuilder

logger = logging.getLogger(__name__)


class AnswerPostProcessor:
    def __init__(
        self,
        *,
        sanitize_debug_text: Callable[[Any], str],
        context_text_from_packet: Callable[[dict[str, Any]], str],
        build_messages: Callable[..., list[dict[str, str]]],
        build_prompt_context_payload: Callable[..., dict[str, Any]],
        build_debug_payload: Callable[..., dict[str, Any]],
        kb_pii_settings: Callable[..., tuple[bool, str, str]],
        pii_depersonalization_service: Callable[[], Any | None] | Any | None,
        max_answer_chars: int,
        insufficient_context_answer: Callable[[], str],
    ) -> None:
        self._sanitize_debug_text = sanitize_debug_text
        self._context_text_from_packet = context_text_from_packet
        self._build_messages = build_messages
        self._build_prompt_context_payload = build_prompt_context_payload
        self._build_debug_payload = build_debug_payload
        self._kb_pii_settings = kb_pii_settings
        self._pii_depersonalization_service = pii_depersonalization_service
        self._max_answer_chars = max_answer_chars
        self._insufficient_context_answer = insufficient_context_answer
        self._source_builder = AnswerSourceBuilder(sanitize_debug_text=sanitize_debug_text)

    def _pii_service(self) -> Any | None:
        if callable(self._pii_depersonalization_service):
            return self._pii_depersonalization_service()
        return self._pii_depersonalization_service

    def build_sources_from_packet(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        return self._source_builder.build_sources_from_packet(packet)

    def _legacy_build_sources_from_packet(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        blocks_by_source: dict[str, dict[str, Any]] = {}
        for block in context_blocks:
            if not isinstance(block, dict):
                continue
            source_id = str(block.get("source_id") or "").strip()
            if not source_id or source_id in blocks_by_source:
                continue
            blocks_by_source[source_id] = block
        for key in ["source_chunks", "evidence_sentences", "top_assertions"]:
            rows.extend(packet.get(key) or [])
        fallback_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        fallback_source_ids: list[str] = []
        for value in [*(packet.get("cited_source_ids") or []), *(packet.get("source_ids") or [])]:
            text = str(value or "").strip()
            if text and text not in fallback_source_ids:
                fallback_source_ids.append(text)
        for item in packet.get("evidence_summary") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("source_id") or "").strip()
            if text and text not in fallback_source_ids:
                fallback_source_ids.append(text)
        for block in packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []:
            if not isinstance(block, dict):
                continue
            text = str(block.get("source_id") or "").strip()
            if text and text not in fallback_source_ids:
                fallback_source_ids.append(text)
        seen: set[tuple[str, str, str]] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            kb_uuid = str(row.get("kb_uuid") or "").strip()
            kb_name = str(row.get("kb_name") or (packet.get("kb_names") or {}).get(kb_uuid) or "").strip()
            point_id = str(
                row.get("source_point_id")
                or row.get("source_id")
                or row.get("id")
                or row.get("point_id")
                or ""
            ).strip()
            source_id = str(row.get("source_id") or "").strip()
            has_source_metadata = bool(
                row.get("display_type")
                or row.get("file_ref")
                or row.get("created_by_label")
                or row.get("created_by") is not None
            )
            if not source_id and has_source_metadata:
                source_id = point_id
            if not source_id and row.get("build_id") and not has_source_metadata:
                continue
            if not source_id:
                source_id = point_id
            if not kb_uuid or not point_id or not source_id:
                continue
            title_raw = str(row.get("source_document_title") or "").strip()
            title_key = " ".join(title_raw.lower().split())
            snippet_value = str(
                row.get("text")
                or row.get("snippet")
                or row.get("payload", {}).get("text")
                or ""
            ).strip()
            snippet_key = " ".join(snippet_value.lower().split())
            source_type_key = str(row.get("source_type") or "").strip().lower()
            display_type_key = str(row.get("display_type") or "").strip().lower()
            is_chat_text_training = (
                source_type_key == "text"
                and (
                    "chatből tanított szöveg" in title_key
                    or "gepel" in display_type_key
                    or "gépel" in display_type_key
                )
            )
            display_key = snippet_key if is_chat_text_training and snippet_key else f"{title_key}|{snippet_key}".strip("|")
            if not display_key:
                display_key = source_id
            item_key = (kb_uuid, display_key, str(row.get("display_type") or "").strip().lower())
            if item_key in seen:
                continue
            seen.add(item_key)
            out.append(
                {
                    "kb_uuid": kb_uuid,
                    "kb_name": self._sanitize_debug_text(kb_name),
                    "point_id": point_id,
                    "source_id": source_id,
                    "title": self._sanitize_debug_text(row.get("source_document_title") or ""),
                    "snippet": self._sanitize_debug_text(
                        (
                            blocks_by_source.get(source_id, {}).get("snippet")
                            or blocks_by_source.get(source_id, {}).get("text")
                            or row.get("text")
                            or row.get("snippet")
                            or ""
                        )
                    ),
                    "source_type": self._sanitize_debug_text(row.get("source_type") or ""),
                    "file_ref": self._sanitize_debug_text(row.get("file_ref") or "") or None,
                    "display_type": self._sanitize_debug_text(row.get("display_type") or ""),
                    "created_by": row.get("created_by"),
                    "created_by_label": self._sanitize_debug_text(row.get("created_by_label") or ""),
                    "created_at": str(row.get("created_at") or "").strip() or None,
                }
            )
            if len(out) >= 8:
                break
        if not out and fallback_kb_uuid:
            for source_id in fallback_source_ids[:8]:
                out.append(
                    {
                        "kb_uuid": fallback_kb_uuid,
                        "kb_name": self._sanitize_debug_text((packet.get("kb_names") or {}).get(fallback_kb_uuid) or ""),
                        "point_id": source_id,
                        "source_id": source_id,
                        "title": f"Forrás {source_id[:8]}",
                        "snippet": "",
                        "source_type": "",
                        "file_ref": None,
                        "display_type": "",
                        "created_by": None,
                        "created_by_label": "",
                        "created_at": None,
                    }
                )
        return out

    @staticmethod
    def is_knowledge_answer(packet: dict[str, Any]) -> bool:
        answer_text = str(packet.get("answer_text") or "").strip()
        answer_mode = str(packet.get("answer_mode") or "no_answer").strip()
        return bool(answer_text and answer_mode and answer_mode != "no_answer")

    @staticmethod
    def chat_evidence(packet: dict[str, Any]) -> list[dict[str, Any]]:
        evidence = packet.get("evidence_summary")
        if isinstance(evidence, list):
            return [dict(item) for item in evidence if isinstance(item, dict)]
        query_debug = packet.get("query_debug") if isinstance(packet.get("query_debug"), dict) else {}
        evidence = query_debug.get("evidence")
        if isinstance(evidence, list):
            return [dict(item) for item in evidence if isinstance(item, dict)]
        return []

    @staticmethod
    def chat_confidence(packet: dict[str, Any]) -> float:
        value = packet.get("synthesis_confidence")
        if value is None and isinstance(packet.get("query_debug"), dict):
            value = packet["query_debug"].get("synthesis_confidence")
        try:
            return round(max(0.0, min(1.0, float(value or 0.0))), 4)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def looks_hungarian_question(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ("á", "é", "í", "ó", "ö", "ő", "ú", "ü", "ű", " mi ", " mit ", "milyen", "hogyan", "hol", "mennyi", "kérlek"))

    @staticmethod
    def looks_english_template_answer(answer: str) -> bool:
        lowered = f" {answer.lower()} "
        return any(
            marker in lowered
            for marker in (
                " the ",
                " currently ",
                " historically ",
                " i found ",
                " direct answer ",
                " related information ",
            )
        )

    @classmethod
    def should_return_direct_knowledge_answer(cls, packet: dict[str, Any], *, question: str = "") -> bool:
        if not cls.is_knowledge_answer(packet):
            return False
        answer_text = str(packet.get("answer_text") or "")
        if cls.looks_hungarian_question(question) and cls.looks_english_template_answer(answer_text):
            return False
        answer_mode = str(packet.get("answer_mode") or "no_answer").strip()
        if answer_mode == "summary":
            return False
        return cls.chat_confidence(packet) >= 0.75

    def build_knowledge_payload(
        self,
        *,
        packet: dict[str, Any],
        debug: bool,
        question: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> dict[str, Any]:
        sources = self.build_sources_from_packet(packet)
        context_preview = self._context_text_from_packet(packet)
        answer_text = str(packet.get("answer_text") or "").strip()
        encoded_answer_text = answer_text
        restored_pii_spans: list[dict[str, Any]] = []
        pii_enabled, pii_sensitivity, _ = self._kb_pii_settings(packet=packet or {}, kb_uuid=None)
        pii_corpus_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        pii_service = self._pii_service()
        if answer_text and pii_enabled and pii_corpus_uuid and pii_service is not None:
            try:
                encoded_answer_text = pii_service.encode_text(
                    corpus_uuid=pii_corpus_uuid,
                    text=answer_text,
                    enabled=True,
                    sensitivity=pii_sensitivity,
                ).text
            except Exception:
                encoded_answer_text = answer_text
        if (
            answer_text
            and pii_enabled
            and pii_service is not None
            and hasattr(pii_service, "detect_plain_spans")
        ):
            try:
                restored_pii_spans = list(
                    pii_service.detect_plain_spans(
                        text=answer_text,
                        enabled=True,
                        sensitivity=pii_sensitivity,
                    )
                    or []
                )
            except Exception:
                logger.debug("chat.knowledge_pii_span_detection_failed", exc_info=True)
        messages = self._build_messages(
            question=question,
            context_text=context_preview,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
        )
        query_profile = packet.get("query_profile") or (packet.get("query_debug") or {}).get("query_profile") or packet.get("query_focus") or {}
        matched_chunks = packet.get("matched_chunks") or []
        matched_claims = packet.get("matched_claims") or []
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        return {
            "answer": answer_text,
            "query_run_id": str(packet.get("query_run_id") or "").strip() or None,
            "answer_mode": str(packet.get("answer_mode") or "no_answer"),
            "answer_source": "knowledge",
            "confidence": self.chat_confidence(packet),
            "evidence": self.chat_evidence(packet),
            "cited_claim_ids": packet.get("cited_claim_ids") or [],
            "cited_sentence_ids": packet.get("cited_sentence_ids") or [],
            "cited_source_ids": packet.get("cited_source_ids") or packet.get("source_ids") or [],
            "citation_records": packet.get("citation_records") or [],
            "query_profile": query_profile,
            "matched_chunks": matched_chunks,
            "claims": matched_claims,
            "context_blocks": context_blocks,
            "sources": sources,
            "encoded_prompt_context": "",
            "restored_pii_spans": restored_pii_spans,
            "prompt_context": self._build_prompt_context_payload(
                question=question,
                messages=messages,
                conversation_history=conversation_history,
                retrieval_history=retrieval_history,
                packet=packet or {},
                context_text=context_preview,
                encoded_answer_text=encoded_answer_text,
            ),
            "debug": (
                self._build_debug_payload(packet=packet or {}, context_text=context_preview, sources=sources)
                if debug
                else None
            ),
        }

    def build_payload(
        self,
        *,
        packet: dict[str, Any],
        answer: str,
        context_text: str,
        context_failed: bool,
        prompt_context: dict[str, Any],
        encoded_prompt_context: str,
        restored_pii_spans: list[dict[str, Any]],
        pii_enabled: bool,
        debug: bool,
        kb_uuid: str | None,
    ) -> dict[str, Any]:
        has_knowledge_context = bool(context_text and not context_failed)
        payload = {
            "answer": str(answer or "")[: self._max_answer_chars],
            "query_run_id": str(packet.get("query_run_id") or "").strip() or None,
            "answer_mode": str(packet.get("answer_mode") or "no_answer"),
            "answer_source": "knowledge_llm" if has_knowledge_context and answer else "llm_fallback" if answer else "none",
            "confidence": self.chat_confidence(packet) if answer else 0.0,
            "evidence": self.chat_evidence(packet) if answer else [],
            "cited_claim_ids": packet.get("cited_claim_ids") or [],
            "cited_sentence_ids": packet.get("cited_sentence_ids") or [],
            "cited_source_ids": packet.get("cited_source_ids") or packet.get("source_ids") or [],
            "query_profile": packet.get("query_profile") or packet.get("query_focus") or {},
            "matched_chunks": packet.get("matched_chunks") or [],
            "claims": packet.get("matched_claims") or [],
            "context_blocks": packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [],
            "citations": packet.get("citations") or [],
            "citation_records": packet.get("citation_records") or [],
            "readiness": packet.get("readiness") or {},
            "sources": self.build_sources_from_packet(packet) if (context_text and not context_failed) or packet.get("sources") else [],
            "prompt_context": prompt_context,
            "encoded_prompt_context": encoded_prompt_context if pii_enabled else "",
            "restored_pii_spans": restored_pii_spans,
        }
        has_grounding_rows = bool(
            packet.get("source_chunks")
            or packet.get("evidence_summary")
            or packet.get("cited_source_ids")
            or packet.get("context_blocks")
            or packet.get("citations")
            or packet.get("sources")
        )
        if has_knowledge_context and payload["answer"] and not payload["sources"] and not has_grounding_rows:
            payload["answer"] = self._insufficient_context_answer()
            payload["answer_mode"] = "no_answer"
            payload["answer_source"] = "none"
            payload["confidence"] = 0.0
            payload["evidence"] = []
            payload["cited_claim_ids"] = []
            payload["cited_sentence_ids"] = []
            payload["cited_source_ids"] = []
        if debug:
            payload["debug"] = self._build_debug_payload(
                packet=packet or {},
                context_text=context_text,
                sources=payload.get("sources") or [],
            )
        return payload


__all__ = ["AnswerPostProcessor"]
