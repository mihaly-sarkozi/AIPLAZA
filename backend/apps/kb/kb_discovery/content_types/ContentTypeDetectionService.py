from __future__ import annotations

import re

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto


class ContentTypeDetectionService:
    def __init__(self) -> None:
        self._detectors = [
            ProcessDetector(),
            FaqDetector(),
            PolicyDetector(),
            GuideDetector(),
        ]

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> dict[str, str]:
        result: dict[str, str] = {}
        for chunk in chunks:
            for detector in self._detectors:
                content_type = detector.detect(chunk.text)
                if content_type:
                    result[chunk.chunk_id] = content_type
                    break
            else:
                result[chunk.chunk_id] = "note"
        return result


class ProcessDetector:
    _STEP = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)

    def detect(self, text: str) -> str | None:
        if self._STEP.search(text):
            return "process"
        return None


class FaqDetector:
    _FAQ = re.compile(r"^\s*(?:mi|milyen|hogyan|miért|mikor)\b.+\?\s*$", re.IGNORECASE | re.MULTILINE)

    def detect(self, text: str) -> str | None:
        if self._FAQ.search(text):
            return "faq"
        return None


class PolicyDetector:
    _POLICY = re.compile(r"\b(kötelező|tilos|szabály|policy|szankció)\b", re.IGNORECASE)

    def detect(self, text: str) -> str | None:
        if self._POLICY.search(text):
            return "policy"
        return None


class GuideDetector:
    _GUIDE = re.compile(r"\b(lépésről lépésre|útmutató|guide|hogyan)\b", re.IGNORECASE)

    def detect(self, text: str) -> str | None:
        if self._GUIDE.search(text):
            return "guide"
        return None


__all__ = [
    "ContentTypeDetectionService",
    "FaqDetector",
    "GuideDetector",
    "PolicyDetector",
    "ProcessDetector",
]
