from __future__ import annotations

import re

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto


class ProcessExtractionService:
    def __init__(self) -> None:
        self._step_detector = StepDetector()
        self._checklist = ChecklistExtractor()
        self._responsibility = ResponsibilityDetector()
        self._scorer = ProcessConfidenceScorer()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for chunk in chunks:
            steps = self._step_detector.detect(chunk.text)
            checklist = self._checklist.extract(chunk.text)
            responsibilities = self._responsibility.detect(chunk.text)
            items = steps + checklist + responsibilities
            if items:
                result[chunk.chunk_id] = items
        return result


class StepDetector:
    _STEP = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)

    def detect(self, text: str) -> list[str]:
        return [f"step:{num}:{label.strip()}" for num, label in self._STEP.findall(text)]


class ChecklistExtractor:
    _ITEM = re.compile(r"^\s*(?:[-*]|\[\s?\])\s+(.+)$", re.MULTILINE)

    def extract(self, text: str) -> list[str]:
        return [f"checklist:{item.strip()}" for item in self._ITEM.findall(text)]


class ResponsibilityDetector:
    _RESP = re.compile(r"\b(felelős|owner|responsible)\s*:?\s*([\wÁÉÍÓÖŐÚÜŰáéíóöőúüű .-]+)", re.IGNORECASE)

    def detect(self, text: str) -> list[str]:
        return [f"responsible:{match.group(2).strip()}" for match in self._RESP.finditer(text)]


class ProcessConfidenceScorer:
    def score(self, item_count: int) -> float:
        return min(1.0, 0.4 + 0.1 * item_count)


__all__ = [
    "ChecklistExtractor",
    "ProcessConfidenceScorer",
    "ProcessExtractionService",
    "ResponsibilityDetector",
    "StepDetector",
]
