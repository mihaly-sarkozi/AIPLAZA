"""
Dedicated VIN (Vehicle Identification Number) recognizer – 17 chars, excludes I,O,Q.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# VIN: exactly 17 alphanumeric (A–H, J–N, P–R, Z, 0–9 per ISO)
_VIN_17 = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
# Labeled: VIN: WVWZZZ1JZXW000001, VIN / alvázszám WDBZZZ9K1BA765432, alvázszám WDBZZZ9K1BA765432
_VIN_LABELED = re.compile(
    r"(?i)\b(?:VIN\s*/\s*alvázszám|VIN\s*:\s*|alvázszám\s*[:\s]*|chassis\s*[:\s]*)\s*([A-HJ-NPR-Z0-9]{17})\b"
)


class VINRecognizer(BaseDetector):
    """Detects VIN (17 characters, optionally with 'VIN:' label)."""

    name = "vin_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        seen: set[tuple[int, int]] = set()
        for m in _VIN_LABELED.finditer(text):
            # Csak a 17 karakter maszkolódik, a "VIN" / "alvázszám" kulcsszó nem
            key = (m.start(1), m.end(1))
            if key in seen:
                continue
            seen.add(key)
            results.append(
                DetectionResult(
                    entity_type=EntityType.VIN,
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.92,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        for m in _VIN_17.finditer(text):
            key = (m.start(), m.end())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                DetectionResult(
                    entity_type=EntityType.VIN,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.72,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
