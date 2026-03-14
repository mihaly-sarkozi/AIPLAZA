# apps/knowledge/pii_gdpr/detectors/technical_identifier_detector.py
"""
Technical identifiers: IP, MAC, IMEI, device/session/cookie IDs.
Pattern + optional context.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


class TechnicalIdentifierDetector(BaseDetector):
    """Detects IP, MAC, IMEI, device/session/cookie identifiers."""

    name = "technical_id"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        # IPv4
        for m in re.finditer(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.IP_ADDRESS,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.80,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        # IPv6 (simplified)
        for m in re.finditer(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b", text):
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
        # MAC
        for m in re.finditer(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", text):
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
        # IMEI with or without label
        for m in re.finditer(r"(?i)\bIMEI\s*:\s*(\d{15})\b", text):
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
        for m in re.finditer(r"\b\d{15}\b", text):
            # Unlabeled 15 digits – lower confidence (could be other IDs)
            results.append(
                DetectionResult(
                    entity_type=EntityType.IMEI,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.55,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.REVIEW_REQUIRED,
                )
            )
        # Session-like IDs
        for m in re.finditer(r"\b(?:sess(?:ion)?_?|sessionid)[\w\-]{8,64}\b", text, re.IGNORECASE):
            results.append(
                DetectionResult(
                    entity_type=EntityType.SESSION_ID,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.78,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
