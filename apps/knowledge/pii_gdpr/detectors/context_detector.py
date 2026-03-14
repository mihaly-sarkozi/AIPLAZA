# apps/knowledge/pii_gdpr/detectors/context_detector.py
"""
Context and keyword-based detector for sensitive-data hints and label context.
Multilingual keywords for EN, HU, ES.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


# (entity_type, keywords_regex, base_confidence) – keywords found in context
_SENSITIVE_HINTS: List[Tuple[EntityType, str, float]] = [
    (EntityType.HEALTH_DATA_HINT, r"(?i)\b(cukorbeteg|diabetes|műtét|surgery|operación|egészség|health|salud|lab result|labor|TAJ|orvosi vizsgálat)\b", 0.65),
    (EntityType.BIOMETRIC_HINT, r"(?i)\b(biometria|biometric|fingerprint|ujjlenyomat|huella|face scan)\b", 0.70),
    (EntityType.POLITICAL_OPINION_HINT, r"(?i)\b(politikai|political|político|párt|party|partido|szavazat|vote|voto)\b", 0.60),
    (EntityType.RELIGION_HINT, r"(?i)\b(vallás|religion|religión|egyház|church|iglesia)\b", 0.65),
    (EntityType.UNION_MEMBERSHIP_HINT, r"(?i)\b(szakszervezet|union|sindical|trade union)\b", 0.65),
    (EntityType.SEXUAL_ORIENTATION_HINT, r"(?i)\b(orientáció|orientation|orientación sexual)\b", 0.60),
]

# Context labels that boost confidence when near a pattern (used by vehicle/technical)
CONTEXT_LABELS: dict[str, List[str]] = {
    "phone": ["telefonszám", "phone", "teléfono", "mobile", "mobil", "móvil", "contact"],
    "address": [
        "cím", "cim", "address", "dirección", "direccion", "lakcím", "postal",
        "utca", "út", "útja", "tér", "tere", "street", "calle", "avenue", "avenida",
        "épület", "emelet", "köz", "negyed", "kerület", "ajtó", "város",
        "lph", "lépcsház", "körút", "sugárút", "sétány", "rakpart", "liget", "park",
        "lakótelep", "telep", "major", "tanya", "zug", "zsákutca", "hrsz", "helyrajzi szám",
        "building", "floor", "district", "quarter", "city", "lives at",
        "edificio", "piso", "puerta", "distrito", "barrio", "ciudad",
    ],
    "vehicle": ["rendszám", "plate", "matrícula", "motorszám", "engine number", "número de motor", "alvázszám", "chassis", "chasis", "VIN"],
    "customer": ["ügyfél", "customer", "cliente", "ügyfélszám", "customer id", "azonosító", "cust", "cl-", "número de cliente"],
    "contract": ["szerződés", "contract", "contrato", "szerződésszám", "contract number", "número de contrato", "flottakód", "fleet"],
    "ticket": ["ticket", "jegy", "incident", "case", "caso", "claim", "panasz", "audit", "clm", "aud"],
    "device": ["device", "dispositivo", "hostname", "asset tag", "network identifier", "printer", "node"],
    "document": ["passport", "útlevél", "pasaporte", "dni", "nif", "nie", "személyi igazolvány", "driver license", "jogosítvány", "jogosítványszám"],
}


class ContextDetector(BaseDetector):
    """Detects sensitive-category hints and provides context scoring for other detectors."""

    name = "context"

    def __init__(self, window_chars: int = 100):
        self.window_chars = window_chars

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for entity_type, pattern, confidence in _SENSITIVE_HINTS:
            for m in re.finditer(pattern, text):
                start = max(0, m.start() - self.window_chars // 2)
                end = min(len(text), m.end() + self.window_chars // 2)
                snippet = text[start:end]
                results.append(
                    DetectionResult(
                        entity_type=entity_type,
                        matched_text=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        language=language,
                        source_detector=self.name,
                        confidence_score=confidence,
                        risk_level=RiskClass.SENSITIVE_DATA,
                        recommended_action=RecommendedAction.REVIEW_REQUIRED,
                        context_before=text[max(0, m.start() - 50):m.start()],
                        context_after=text[m.end():min(len(text), m.end() + 50)],
                    )
                )
        return results

    @staticmethod
    def score_context(text: str, start: int, end: int, label_key: str) -> float:
        """Return a context boost (0.0–0.2) if label keywords appear near (start,end)."""
        labels = CONTEXT_LABELS.get(label_key, [])
        if not labels:
            return 0.0
        window = 80
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        ctx = text[ctx_start:ctx_end].lower()
        for kw in labels:
            if kw.lower() in ctx:
                return 0.15
        return 0.0
