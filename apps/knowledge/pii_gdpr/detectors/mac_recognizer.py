"""
Dedicated MAC address recognizer.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# MAC: 6 groups of 2 hex digits, separator - or :
_MAC_PATTERN = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")


class MACRecognizer(BaseDetector):
    """Detects MAC addresses (colon or hyphen separated)."""

    name = "mac_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for m in _MAC_PATTERN.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.MAC_ADDRESS,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.90,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
