from __future__ import annotations

import re

from apps.kb.kb_discovery.processes.ProcessConfidenceScorer import ProcessConfidenceScorer


class StepDetector:
    _STEP = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)

    def detect(self, text: str) -> list[tuple[int, str]]:
        return [(int(num), label.strip()) for num, label in self._STEP.findall(text)]


__all__ = ["StepDetector"]
