"""
Dedicated engine number and chassis number recognizer (context + pattern).
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# Labeled engine/chassis (HU, EN, ES)
_ENGINE_CHASSIS_LABELED = re.compile(
    r"(?i)\b(?:"
    r"motorszám|alvázszám|"
    r"engine\s*number|"
    r"número\s*de\s*motor|número\s*de\s*chasis|"
    r"chassis|chasis"
    r")\s*[:\-]?\s*([A-Z0-9\-]{8,20})\b"
)


class EngineIDRecognizer(BaseDetector):
    """Detects engine and chassis identifiers when labeled (e.g. 'engine number: AB12CD345678')."""

    name = "engine_id_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for m in _ENGINE_CHASSIS_LABELED.finditer(text):
            # Prefer ENGINE_IDENTIFIER for "engine number" / "motorszám"; CHASSIS for "chassis" / "alváz"
            ctx = text[max(0, m.start() - 40) : m.end()].lower()
            if "chassis" in ctx or "alváz" in ctx or "chasis" in ctx:
                entity = EntityType.CHASSIS_IDENTIFIER
            else:
                entity = EntityType.ENGINE_IDENTIFIER
            # Csak az azonosító maszkolódik, az "alvázszám" / "motorszám" kulcsszó nem
            results.append(
                DetectionResult(
                    entity_type=entity,
                    matched_text=m.group(1),
                    start=m.start(1),
                    end=m.end(1),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.85,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK,
                )
            )
        return results
