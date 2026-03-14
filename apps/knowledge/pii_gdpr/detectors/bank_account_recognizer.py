"""
Dedicated non-IBAN bank account number recognizer (e.g. HU 8-8-8, DE style).
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# Hungarian: 8-8-8 digits, optional dash/space
_HU_ACCOUNT = re.compile(r"\b\d{8}[\- ]?\d{8}[\- ]?\d{8}\b")
# Generic: "account" / "számla" / "cuenta" + digits (10–24)
_ACCOUNT_LABELED = re.compile(
    r"(?i)\b(?:account|számla|szamla|cuenta|bankszámla)\s*[:\-]?\s*(\d{10,24})\b"
)


class BankAccountRecognizer(BaseDetector):
    """Detects non-IBAN bank account formats (HU 8-8-8 and labeled account numbers)."""

    name = "bank_account_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for m in _HU_ACCOUNT.finditer(text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.BANK_ACCOUNT_NUMBER,
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
        for m in _ACCOUNT_LABELED.finditer(text):
            # Avoid duplicate span from HU pattern
            if any(r.start == m.start() and r.end == m.end() for r in results):
                continue
            results.append(
                DetectionResult(
                    entity_type=EntityType.BANK_ACCOUNT_NUMBER,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.78,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
