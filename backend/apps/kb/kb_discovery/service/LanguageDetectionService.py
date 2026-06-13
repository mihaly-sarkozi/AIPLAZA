from __future__ import annotations

import re

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.LanguageDetectionResult import LanguageDetectionResult
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.languages.language_profiles import LANGUAGE_MARKERS
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository


class LanguageDetectionService:
    _TOKEN = re.compile(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+", re.UNICODE)

    def __init__(self, job_repository: DiscoveryJobRepository) -> None:
        self._job_repository = job_repository

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> LanguageDetectionResult:
        chunk_languages: dict[str, str] = {}
        scores = {lang: 0 for lang in (SupportedLanguage.HU, SupportedLanguage.EN, SupportedLanguage.ES)}

        for chunk in chunks:
            lang, confidence = self._detect_chunk(chunk.text)
            chunk_languages[chunk.chunk_id] = lang.value
            scores[lang] = scores.get(lang, 0) + confidence

        if not chunks:
            primary = SupportedLanguage.UNKNOWN
            confidence = 0.0
        else:
            primary = max(scores, key=lambda lang: scores[lang])
            total = sum(scores.values()) or 1.0
            confidence = round(scores[primary] / total, 4)
            if scores[primary] <= 0:
                primary = SupportedLanguage.UNKNOWN
                confidence = 0.0

        metadata = {
            "language_code": primary.value,
            "language_confidence": confidence,
            "chunk_languages": chunk_languages,
        }
        self._job_repository.update_metadata(ctx.job_id, metadata)
        return LanguageDetectionResult(
            language_code=primary.value,
            language_confidence=confidence,
            chunk_languages=chunk_languages,
        )

    def _detect_chunk(self, text: str) -> tuple[SupportedLanguage, float]:
        tokens = {token.lower() for token in self._TOKEN.findall(text)}
        if not tokens:
            return SupportedLanguage.UNKNOWN, 0.0
        best = SupportedLanguage.UNKNOWN
        best_score = 0.0
        for language, markers in LANGUAGE_MARKERS.items():
            hits = len(tokens & markers)
            score = hits / max(len(tokens), 1)
            if score > best_score:
                best_score = score
                best = language
        if best_score == 0.0:
            if any(ch in text for ch in "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"):
                return SupportedLanguage.HU, 0.5
            return SupportedLanguage.UNKNOWN, 0.0
        return best, best_score


__all__ = ["LanguageDetectionService"]
