# apps/knowledge/pii_gdpr/detectors/vehicle_detector.py
"""
Vehicle-related detector: registration plates, VIN, engine/chassis identifiers.
Uses pattern + context (keywords) to adjust confidence.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector
from apps.knowledge.pii_gdpr.detectors.context_detector import ContextDetector

# Context keywords that boost vehicle-related confidence (EN, HU, ES)
_VEHICLE_BOOST = [
    # Hungarian
    "rendszám", "motorszám", "alvázszám", "ügyfélszám", "szerződésszám",
    # English
    "license plate", "engine number", "customer id", "contract number", "vehicle",
    # Spanish
    "matrícula", "número de motor", "número de chasis", "cliente", "contrato", "vehículo",
    # Common
    "VIN", "plate", "chassis", "chasis", "jármű",
]
# Context that may reduce (invoice, SKU, product)
_VEHICLE_REDUCE = ["invoice", "számla", "factura", "SKU", "product", "termék", "cikkszám"]


class VehicleDetector(BaseDetector):
    """Detects vehicle registration, VIN, engine and chassis identifiers with context scoring."""

    name = "vehicle"

    def __init__(self, context_window: int = 80):
        self.context_window = context_window

    def _context_boost(self, text: str, start: int, end: int) -> float:
        ctx_start = max(0, start - self.context_window)
        ctx_end = min(len(text), end + self.context_window)
        ctx = text[ctx_start:ctx_end].lower()
        for kw in _VEHICLE_BOOST:
            if kw.lower() in ctx:
                return 0.15
        return 0.0

    def _context_penalty(self, text: str, start: int, end: int) -> float:
        ctx_start = max(0, start - self.context_window)
        ctx_end = min(len(text), end + self.context_window)
        ctx = text[ctx_start:ctx_end].lower()
        for kw in _VEHICLE_REDUCE:
            if kw.lower() in ctx:
                return -0.20
        return 0.0

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        # VIN 17 chars (exclude I,O,Q)
        for m in re.finditer(r"\b[A-HJ-NPR-Z0-9]{17}\b", text):
            base = 0.72
            base += self._context_boost(text, m.start(), m.end())
            base += self._context_penalty(text, m.start(), m.end())
            score = max(0.35, min(0.95, base))
            results.append(
                DetectionResult(
                    entity_type=EntityType.VIN,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=score,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK if score >= 0.85 else RecommendedAction.REVIEW_REQUIRED,
                )
            )
        # Labeled VIN
        for m in re.finditer(r"(?i)\bVIN\s*:\s*([A-HJ-NPR-Z0-9]{17})\b", text):
            results.append(
                DetectionResult(
                    entity_type=EntityType.VIN,
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
        # Plates: HU 3 letter 3 digit; HU new 2-2-2-2; ES 4 digit 3 letter
        for m in re.finditer(r"\b[A-Z]{3}[- ]?\d{3}\b", text):
            base = 0.75 + self._context_boost(text, m.start(), m.end()) + self._context_penalty(text, m.start(), m.end())
            score = max(0.40, min(0.92, base))
            results.append(
                DetectionResult(
                    entity_type=EntityType.VEHICLE_REGISTRATION,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=score,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK if score >= 0.85 else RecommendedAction.REVIEW_REQUIRED,
                )
            )
        for m in re.finditer(r"\b[A-Z]{2}[- ]?\d{2}[- ]?[A-Z]{2}[- ]?\d{2}\b", text):
            base = 0.76 + self._context_boost(text, m.start(), m.end()) + self._context_penalty(text, m.start(), m.end())
            score = max(0.40, min(0.92, base))
            results.append(
                DetectionResult(
                    entity_type=EntityType.VEHICLE_REGISTRATION,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=score,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK if score >= 0.85 else RecommendedAction.REVIEW_REQUIRED,
                )
            )
        for m in re.finditer(r"\b\d{4}\s+[A-Z]{3}\b", text):
            base = 0.74 + self._context_boost(text, m.start(), m.end()) + self._context_penalty(text, m.start(), m.end())
            score = max(0.40, min(0.92, base))
            results.append(
                DetectionResult(
                    entity_type=EntityType.VEHICLE_REGISTRATION,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=score,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.MASK if score >= 0.85 else RecommendedAction.REVIEW_REQUIRED,
                )
            )
        # Engine / chassis: csak az azonosító maszkolódik, a kulcsszó nem
        for m in re.finditer(
            r"(?i)\b(?:motorszám|engine\s*number|número\s*de\s*motor|número\s*de\s*chasis|chassis|alvázszám|chasis)\s*[:\-]?\s*([A-Z0-9\-]{8,20})\b",
            text,
        ):
            ctx = text[max(0, m.start() - 40) : m.end()].lower()
            entity = EntityType.CHASSIS_IDENTIFIER if any(x in ctx for x in ("chassis", "alváz", "chasis")) else EntityType.ENGINE_IDENTIFIER
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
