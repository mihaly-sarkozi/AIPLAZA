"""
Dedicated government / document identifiers: TAJ, tax ID, passport, driver license.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# TAJ (HU): 9 digits in 3-3-3, optional spaces (exclude when part of Spanish phone +34 / 0034)
_TAJ = re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b")
_SPANISH_PHONE_PREFIX = re.compile(r"(?:\+34|0034)\s*$")
# Hungarian tax ID: 8 digit + 1 + 2, vagy 10 számjegy "adóazonosító" kontextusban
_TAX_ID = re.compile(r"\b\d{8}[\- ]?\d{1}[\- ]?\d{2}\b")
_TAX_ID_10_DIGIT = re.compile(r"\b\d{10}\b")
_TAX_CONTEXT = re.compile(r"(?i)adóazonosító\s*(?:jele)?\s*")
# Passport: csak az azonosító maszkolódik (kulcsszó nem)
_PASSPORT = re.compile(
    r"(?i)\b(?:passport|útlevél|pasaporte)(?:\s*:\s*|\s+(?:number|szám|número)\s+(?:is\s+)?)([A-Z0-9]{6,12})\b"
)
# Driver license: csak az azonosító
_DRIVER_LICENSE = re.compile(
    r"(?i)\b(?:driver|jogosítvány|permiso)\s*(?:license|number|szám|número)?\s*:\s*([A-Z0-9]{6,12})\b"
)
_DRIVER_LICENSE_ALT = re.compile(
    r"(?i)\b(?:jogosítványszám|jogosítvány\s+száma?|permiso\s+de\s+conducir)\s*[:\-]?\s*([A-Z0-9\-]{6,15})\b"
)
# NIE: csak az azonosító (X/Y/Z + 7 számjegy + betű)
_NIE = re.compile(r"(?i)\b(?:(?:su\s+)?NIE\s*[:\-]?\s*)([XYZ]\d{7}[A-Z])\b")
# Személyi igazolvány – csak a szám/azonosító (pl. BB654321), kulcsszó nem maszkolódik
_PERSONAL_ID_DOC = re.compile(
    r"(?i)\b(?:személyi igazolvány(?:szám)?|személyi igazolvány száma)\s*[:\-]?\s*([A-Z0-9]{6,15})\b"
)


class DocumentIdentifiersRecognizer(BaseDetector):
    """Detects TAJ, tax ID, passport number, driver license number."""

    name = "document_identifiers_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for m in _TAJ.finditer(text):
            # Skip if this 9-digit block is part of Spanish phone +34 / 0034
            prefix = text[max(0, m.start() - 6) : m.start()]
            if _SPANISH_PHONE_PREFIX.search(prefix):
                continue
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
        for m in _TAX_ID_10_DIGIT.finditer(text):
            ctx_before = text[max(0, m.start() - 60) : m.start()]
            if _TAX_CONTEXT.search(ctx_before):
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
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
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
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.82,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _DRIVER_LICENSE_ALT.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.DRIVER_LICENSE_NUMBER,
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.88,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _NIE.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.PERSONAL_ID,
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.90,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _PERSONAL_ID_DOC.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.PERSONAL_ID,
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.88,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
