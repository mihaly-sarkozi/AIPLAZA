from __future__ import annotations

import re
from typing import Any


class BuildSearchQueryService:
    _HU_CHARS = re.compile(r"[áéíóöőúüű]", re.I)

    def build(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, Any]] | None = None,
        knowledge_base_id: str | None = None,
        channel_id: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        normalized = " ".join(str(question or "").strip().split())
        rewritten = self._rewrite_followup(normalized, conversation_history)
        language_code = self._detect_language(rewritten or normalized)
        filters: dict[str, Any] = {"knowledge_base_id": knowledge_base_id}
        if language_code:
            filters["language_code"] = language_code
        if channel_id:
            filters["channel_id"] = channel_id
        return {
            "normalized_question": normalized,
            "rewritten_question": rewritten or normalized,
            "language_code": language_code,
            "filters": filters,
        }

    def _detect_language(self, text: str) -> str | None:
        if self._HU_CHARS.search(text):
            return "hu"
        lowered = text.lower()
        if any(token in lowered for token in (" the ", " and ", " what ", " how ")):
            return "en"
        return "hu" if text else None

    def _rewrite_followup(
        self,
        question: str,
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        if not conversation_history:
            return question
        lowered = question.lower()
        followup_markers = ("erről", "ezt", "azt", "ő", "őt", "this", "that", "it")
        if not any(marker in lowered for marker in followup_markers):
            return question
        last_user = ""
        for row in reversed(conversation_history):
            role = str(row.get("role") or "").strip().lower()
            content = str(row.get("content") or row.get("text") or "").strip()
            if role == "user" and content:
                last_user = content
                break
        if not last_user:
            return question
        return f"{last_user} — {question}"


__all__ = ["BuildSearchQueryService"]
