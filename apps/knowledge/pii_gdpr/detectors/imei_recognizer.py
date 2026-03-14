"""
Dedicated IMEI recognizer (15 digits; optional label).
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# Labeled: IMEI: 490154203237518
_IMEI_LABELED = re.compile(r"(?i)\bIMEI\s*:\s*(\d{15})\b")
# Standalone 15 digits (lower confidence – can be other IDs)
_IMEI_15 = re.compile(r"\b\d{15}\b")


class IMEIRecognizer(BaseDetector):
    """Detects IMEI (15 digits), with or without 'IMEI:' label."""

    name = "imei_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        seen: set[tuple[int, int]] = set()
        for m in _IMEI_LABELED.finditer(text):
            key = (m.start(), m.end())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                DetectionResult(
                    entity_type=EntityType.IMEI,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.92,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _IMEI_15.finditer(text):
            key = (m.start(), m.end())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                DetectionResult(
                    entity_type=EntityType.IMEI,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.58,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.REVIEW_REQUIRED,
                )
            )
        return results
