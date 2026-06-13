from __future__ import annotations

import re

from apps.kb.kb_discovery.content_types.content_type_result import ContentTypeCandidate, ContentTypeResult
from apps.kb.kb_discovery.content_types.ExtraContentTypeDetectors import (
    DefinitionDetector,
    NoteDetector,
    ReferenceDetector,
    WarningDetector,
)
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto

_CHUNK_TYPE_MAP = {
    "table": "table",
    "list": "list",
    "step": "step",
    "warning": "warning",
    "note": "note",
}


class ProcessDetector:
    _STEP = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)
    _IMPERATIVE = re.compile(r"\b(kattint|nyissa|kattints|click|open|select)\b", re.IGNORECASE)
    name = "process_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        signals: list[str] = []
        if self._STEP.search(text):
            signals.append("numbered_steps")
        if self._IMPERATIVE.search(text):
            signals.append("imperative_verbs")
        if signals:
            return ("process", 0.86 if "numbered_steps" in signals else 0.74, tuple(signals))
        return None


class FaqDetector:
    _FAQ = re.compile(
        r"^\s*(?:mi|milyen|hogyan|miért|mikor|what|how|why|when|qué|cómo|por qué)\b.+\?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    name = "faq_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._FAQ.search(text):
            return ("faq", 0.84, ("question_sentence",))
        return None


class PolicyDetector:
    _POLICY = re.compile(r"\b(kötelező|tilos|szabály|policy|szankció|must not|prohibited)\b", re.IGNORECASE)
    name = "policy_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._POLICY.search(text):
            return ("policy", 0.8, ("policy_marker",))
        return None


class GuideDetector:
    _GUIDE = re.compile(r"\b(lépésről lépésre|útmutató|guide|how to|tutorial)\b", re.IGNORECASE)
    name = "guide_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._GUIDE.search(text):
            return ("guide", 0.76, ("guide_marker",))
        return None


class ContentTypeDetectionService:
    _TEXT_DETECTORS = (
        FaqDetector(),
        ProcessDetector(),
        PolicyDetector(),
        GuideDetector(),
        DefinitionDetector(),
        ReferenceDetector(),
        NoteDetector(),
        WarningDetector(),
    )

    def detect_for_chunk(self, chunk: DiscoveryChunkDto) -> ContentTypeResult:
        chunk_type = (chunk.chunk_type or "").strip().lower()
        mapped = _CHUNK_TYPE_MAP.get(chunk_type)
        if mapped:
            return ContentTypeResult(
                content_type=mapped,
                confidence=0.92,
                candidates=(ContentTypeCandidate(mapped, 0.92, "chunk_type", ("chunk_type",)),),
                detectors=("chunk_type",),
                signals=(f"chunk_type:{chunk_type}",),
                metadata={"winner_source": "chunk_type"},
            )

        candidates: list[ContentTypeCandidate] = []
        for detector in self._TEXT_DETECTORS:
            result = detector.detect(chunk.text)
            if result is None:
                continue
            content_type, confidence, signals = result
            candidates.append(
                ContentTypeCandidate(content_type, confidence, detector.name, signals)
            )

        if not candidates:
            return ContentTypeResult(
                content_type="general_text",
                confidence=0.45,
                candidates=(),
                detectors=(),
                signals=(),
                metadata={"winner_source": "default"},
            )

        candidates.sort(key=lambda item: (-item.confidence, item.content_type))
        winner = candidates[0]
        return ContentTypeResult(
            content_type=winner.content_type,
            confidence=winner.confidence,
            candidates=tuple(candidates),
            detectors=tuple(item.detector for item in candidates),
            signals=winner.signals,
            metadata={
                "winner_source": winner.detector,
                "content_type_detection": {
                    "detectors": [item.detector for item in candidates],
                    "winner": winner.content_type,
                    "winner_confidence": winner.confidence,
                    "candidates": [
                        {"type": item.content_type, "confidence": item.confidence}
                        for item in candidates
                    ],
                    "signals": list(winner.signals),
                },
            },
        )


__all__ = [
    "ContentTypeDetectionService",
    "FaqDetector",
    "GuideDetector",
    "PolicyDetector",
    "ProcessDetector",
]
