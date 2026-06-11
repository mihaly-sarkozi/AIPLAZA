from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/LlmEnrichmentAdapter.py
# Feladat: Chunk-szintű AI enrichment — összefoglaló, kulcsszavak, témák, tartalomtípus,
# nyelv, nehézség, fontosság, megválaszolható kérdések.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.adapters.LlmCompletionAdapter import LlmCompletionAdapter
from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto

_SYSTEM_PROMPT = (
    "Te egy tudástár enrichment komponense vagy. A kapott szövegrészhez metaadatot készítesz. "
    "Kizárólag érvényes JSON-nal válaszolj, a következő formában: "
    '{"summary": "rövid összefoglaló a szöveg nyelvén", "keywords": ["..."], "topics": ["..."], '
    '"content_type": "process|faq|policy|reference|other", "language": "ISO 639-1 kód", '
    '"difficulty": "basic|intermediate|advanced", "importance": 0.0, '
    '"possible_questions": ["..."], "confidence": 0.0}. '
    "Az importance és confidence 0 és 1 közötti szám. Maximum 8 kulcsszót, 4 témát és 5 kérdést adj."
)

_ALLOWED_DIFFICULTIES = {"basic", "intermediate", "advanced"}


class LlmEnrichmentAdapter:
    """``EnrichmentInterface`` implementáció."""

    def __init__(self, llm: LlmCompletionAdapter) -> None:
        self._llm = llm

    def enrich_chunk(self, chunk_id: str, text: str) -> KnowledgeEnrichmentDto:
        payload = self._llm.complete_json(system=_SYSTEM_PROMPT, user=text)
        if not isinstance(payload, dict):
            payload = {}
        difficulty = str(payload.get("difficulty", "") or "").strip().lower()
        return KnowledgeEnrichmentDto(
            chunk_id=chunk_id,
            summary=str(payload.get("summary", "") or "").strip(),
            keywords=self._string_tuple(payload.get("keywords"), limit=8),
            topics=self._string_tuple(payload.get("topics"), limit=4),
            possible_questions=self._string_tuple(payload.get("possible_questions"), limit=5),
            content_type=str(payload.get("content_type", "") or "").strip().lower() or None,
            language=str(payload.get("language", "") or "").strip().lower()[:8] or None,
            difficulty=difficulty if difficulty in _ALLOWED_DIFFICULTIES else None,
            importance=self._clamped_float(payload.get("importance")),
            confidence=self._clamped_float(payload.get("confidence")),
        )

    @staticmethod
    def _string_tuple(value: object, *, limit: int) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        items = [str(item).strip() for item in value if str(item).strip()]
        return tuple(items[:limit])

    @staticmethod
    def _clamped_float(value: object) -> float:
        try:
            return min(1.0, max(0.0, float(value)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0


__all__ = ["LlmEnrichmentAdapter"]
