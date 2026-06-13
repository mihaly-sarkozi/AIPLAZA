from __future__ import annotations

import re
from collections import Counter

from apps.kb.kb_discovery.dto.ChunkLanguageResult import ChunkLanguageResult
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.LanguageDetectionResult import LanguageDetectionResult
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.languages.language_profiles import LANGUAGE_MARKERS
from apps.kb.kb_discovery.ports.ChunkLanguageWriterPort import ChunkLanguageWriterPort
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
from apps.kb.shared.contracts import ChunkLanguageUpdate

_DETECTED_BY = "local_stopword_marker"
_MIXED_RATIO = 0.7


class LanguageDetectionService:
    _TOKEN = re.compile(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+", re.UNICODE)

    def __init__(
        self,
        job_repository: DiscoveryJobRepository,
        chunk_language_writer: ChunkLanguageWriterPort | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._chunk_language_writer = chunk_language_writer

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> LanguageDetectionResult:
        chunk_results: list[ChunkLanguageResult] = []
        distribution: Counter[str] = Counter()
        weighted_scores: Counter[str] = Counter()

        for chunk in chunks:
            result = self._detect_chunk(chunk)
            chunk_results.append(result)
            distribution[result.language_code] += 1
            weighted_scores[result.language_code] += result.language_confidence

        if self._chunk_language_writer is not None and chunk_results:
            self._chunk_language_writer.bulk_update_chunk_language(
                [
                    ChunkLanguageUpdate(
                        chunk_id=item.chunk_id,
                        language_code=item.language_code,
                        language_confidence=item.language_confidence,
                        language_detected_by=item.language_detected_by,
                        language_metadata=dict(item.language_metadata),
                    )
                    for item in chunk_results
                ]
            )

        if not chunks:
            document_language = SupportedLanguage.UNKNOWN.value
            document_confidence = 0.0
        else:
            document_language, document_confidence = self._document_language(weighted_scores, distribution)

        metadata = {
            "document_language_code": document_language,
            "document_language_confidence": document_confidence,
            "language_distribution": dict(distribution),
        }
        self._job_repository.update_metadata(ctx.job_id, metadata)

        chunk_languages = {item.chunk_id: item.language_code for item in chunk_results}
        return LanguageDetectionResult(
            language_code=document_language,
            language_confidence=document_confidence,
            chunk_languages=chunk_languages,
            chunks_checked=len(chunks),
            language_distribution=dict(distribution),
            chunk_results=chunk_results,
        )

    def _detect_chunk(self, chunk: DiscoveryChunkDto) -> ChunkLanguageResult:
        hints = list(chunk.metadata.get("language_hints") or [])
        tokens = {token.lower() for token in self._TOKEN.findall(chunk.text)}
        scores: dict[str, float] = {
            SupportedLanguage.HU.value: 0.0,
            SupportedLanguage.EN.value: 0.0,
            SupportedLanguage.ES.value: 0.0,
        }
        matched_markers: dict[str, list[str]] = {code: [] for code in scores}

        if not tokens:
            return ChunkLanguageResult(
                chunk_id=chunk.chunk_id,
                language_code=SupportedLanguage.UNKNOWN.value,
                language_confidence=0.0,
                language_detected_by=_DETECTED_BY,
                language_metadata={
                    "code": SupportedLanguage.UNKNOWN.value,
                    "confidence": 0.0,
                    "detected_by": _DETECTED_BY,
                    "hints": hints,
                    "matched_markers": {},
                    "scores": scores,
                },
            )

        for language, markers in LANGUAGE_MARKERS.items():
            hits = sorted(tokens & markers)
            score = len(hits) / max(len(tokens), 1)
            if hints and language.value in hints:
                score = min(1.0, score + 0.05)
            scores[language.value] = round(score, 4)
            matched_markers[language.value] = hits[:10]

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_code, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0

        if best_score == 0.0:
            if any(ch in chunk.text for ch in "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"):
                primary_lang = SupportedLanguage.HU.value
                best_code = SupportedLanguage.HU.value
                best_score = 0.5
            else:
                primary_lang = SupportedLanguage.UNKNOWN.value
                best_code = SupportedLanguage.UNKNOWN.value
                best_score = 0.0
        elif second_score > 0 and second_score >= best_score * _MIXED_RATIO:
            primary_lang = best_code
            best_code = SupportedLanguage.MIXED.value
            best_score = round((best_score + second_score) / 2, 4)
        else:
            primary_lang = best_code

        language_metadata = {
            "code": best_code,
            "confidence": best_score,
            "detected_by": _DETECTED_BY,
            "hints": hints,
            "matched_markers": matched_markers.get(primary_lang, []),
            "scores": scores,
        }
        return ChunkLanguageResult(
            chunk_id=chunk.chunk_id,
            language_code=best_code,
            language_confidence=best_score,
            language_detected_by=_DETECTED_BY,
            language_metadata=language_metadata,
        )

    @staticmethod
    def _document_language(
        weighted_scores: Counter[str],
        distribution: Counter[str],
    ) -> tuple[str, float]:
        if not distribution:
            return SupportedLanguage.UNKNOWN.value, 0.0
        primary = max(weighted_scores, key=lambda code: weighted_scores[code])
        total_weight = sum(weighted_scores.values()) or 1.0
        confidence = round(weighted_scores[primary] / total_weight, 4)
        if weighted_scores[primary] <= 0:
            return SupportedLanguage.UNKNOWN.value, 0.0
        return primary, confidence


__all__ = ["LanguageDetectionService"]
