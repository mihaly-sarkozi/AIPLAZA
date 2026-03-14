"""
Dedicated government / document identifiers: TAJ, tax ID, passport, driver license.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# TAJ (HU): 9 digits in 3-3-3, optional spaces
_TAJ = re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b")
# Hungarian tax ID: 8 digit + 1 + 2
_TAX_ID = re.compile(r"\b\d{8}[\- ]?\d{1}[\- ]?\d{2}\b")
# Passport: label + alphanumeric
_PASSPORT = re.compile(r"(?i)\b(?:passport|útlevél|pasaporte)\s*:\s*[A-Z0-9]{6,12}\b")
# Driver license: label + alphanumeric
_DRIVER_LICENSE = re.compile(
    r"(?i)\b(?:driver|jogosítvány|permiso)\s*(?:license|number|szám|número)?\s*:\s*[A-Z0-9]{6,12}\b"
)


class DocumentIdentifiersRecognizer(BaseDetector):
    """Detects TAJ, tax ID, passport number, driver license number."""

    name = "document_identifiers_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for m in _TAJ.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.PERSONAL_ID,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.90,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _TAX_ID.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.TAX_ID,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.90,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _PASSPORT.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.PASSPORT_NUMBER,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.85,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _DRIVER_LICENSE.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.DRIVER_LICENSE_NUMBER,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.82,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
