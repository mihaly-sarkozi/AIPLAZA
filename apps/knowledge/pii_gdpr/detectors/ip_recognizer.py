"""
Dedicated IP address recognizer: IPv4 and IPv6.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# IPv4: 1-3 digits per octet (no validation of 0-255 here to avoid false negatives)
_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# IPv6: full form 8 groups of 1-4 hex digits
_IPV6_PATTERN = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")


class IPRecognizer(BaseDetector):
    """Detects IPv4 and IPv6 addresses."""

    name = "ip_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for m in _IPV4_PATTERN.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.IP_ADDRESS,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.82,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _IPV6_PATTERN.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.IP_ADDRESS,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.88,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
