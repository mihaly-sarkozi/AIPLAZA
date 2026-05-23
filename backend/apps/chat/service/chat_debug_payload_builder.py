# backend/apps/chat/service/chat_debug_payload_builder.py
# Owns chat debug payload construction and debug-safe value normalization.

from __future__ import annotations

from typing import Any, Callable

from apps.chat.service.chat_text_utils import sanitize_debug_text, sanitize_debug_value


class ChatDebugPayloadBuilder:
    def __init__(self, *, dedupe_keep_order: Callable[[list[str]], list[str]]) -> None:
        self._dedupe_keep_order = dedupe_keep_order

    @staticmethod
    def sanitize_text(value: Any) -> str:
        return sanitize_debug_text(value)

    @staticmethod
    def sanitize_value(value: Any) -> Any:
        return sanitize_debug_value(value)

    def build(self, packet: dict[str, Any], context_text: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
        top_assertions = (
            packet.get("primary_assertions")
            or packet.get("seed_assertions")
            or packet.get("summary_assertions")
            or packet.get("top_assertions")
            or []
        )
        evidence_sentences = packet.get("evidence_sentences") or []
        source_chunks = packet.get("source_chunks") or []
        related_entities = packet.get("related_entities") or []
        top_assertion_ids = [
            str(row.get("id"))
            for row in top_assertions
            if row.get("id") is not None
        ]
        source_point_ids = self._dedupe_keep_order(
            [
                str(item.get("point_id") or "").strip()
                for item in (sources or [])
                if str(item.get("point_id") or "").strip()
            ]
        )
        return {
            "query_focus": self.sanitize_value(packet.get("query_focus") or {}),
            "query_profile": self.sanitize_value(packet.get("query_profile") or (packet.get("query_debug") or {}).get("query_profile") or {}),
            "matched_chunks": self.sanitize_value(packet.get("matched_chunks") or []),
            "claims": self.sanitize_value(packet.get("matched_claims") or []),
            "context_blocks": self.sanitize_value(packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []),
            "answer_verification": self.sanitize_value(
                packet.get("answer_verification") or (packet.get("query_debug") or {}).get("answer_verification") or {}
            ),
            "scoring_summary": self.sanitize_value(packet.get("scoring_summary") or {}),
            "top_assertion_count": len(top_assertions),
            "evidence_sentence_count": len(evidence_sentences),
            "source_chunk_count": len(source_chunks),
            "related_entity_count": len(related_entities),
            "context_preview": self.sanitize_text((context_text or "")[:500]),
            "top_assertion_ids": top_assertion_ids[:12],
            "source_point_ids": source_point_ids[:12],
        }


__all__ = ["ChatDebugPayloadBuilder"]
