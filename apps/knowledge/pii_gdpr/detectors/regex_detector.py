# apps/knowledge/pii_gdpr/detectors/regex_detector.py
"""
Rule-based regex detector for deterministic PII patterns.
Multilingual patterns for EN, HU, ES where relevant.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


# (entity_type, pattern, base_confidence, risk_class)
_REGEX_RULES: List[Tuple[EntityType, str, float, RiskClass]] = [
    # Email
    (EntityType.EMAIL_ADDRESS, r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 0.95, RiskClass.DIRECT_PII),
    # Phone – international, HU, ES
    (EntityType.PHONE_NUMBER, r"\+\d{1,3}[\s\-.]?(?:\d[\s\-.]?){8,14}\d\b", 0.88, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"\b(?:\+36|06)[\s\-/]?\d{1,2}[\s\-/]?\d{3}[\s\-/]?\d{4}\b", 0.92, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"\b(?:\+34|0034)?[\s\-]?\d{2,3}[\s\-]?\d{3}[\s\-]?\d{3}\b", 0.85, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"\b\d{2}[\s\-/]\d{3}[\s\-/]\d{4}\b", 0.75, RiskClass.DIRECT_PII),
    # IBAN
    (EntityType.IBAN, r"\b[A-Z]{2}\d{2}\s?(?:[A-Z0-9]\s?){4}(?:[A-Z0-9]\s?){4,28}\b", 0.92, RiskClass.DIRECT_PII),
    # Bank account HU style
    (EntityType.BANK_ACCOUNT_NUMBER, r"\b\d{8}[\- ]?\d{8}[\- ]?\d{8}\b", 0.85, RiskClass.DIRECT_PII),
    # Payment card (simplified – 4 groups of 4 digits)
    (EntityType.PAYMENT_CARD_NUMBER, r"\b(?:\d{4}[\s\-]){3}\d{4}\b", 0.82, RiskClass.DIRECT_PII),
    # Általános dátum (dátum) – nincs születési kontextus
    (EntityType.DATE, r"\b(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DATE, r"\b(?:0[1-9]|[12]\d|3[01])[.\-/](?:0[1-9]|1[0-2])[.\-/](?:19|20)\d{2}\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DATE, r"\b(?:19|20)\d{2}\.\s*(?:0[1-9]|1[0-2])\.\s*(?:0[1-9]|[12]\d|3[01])\.?", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # Születési dátum (születési_dátum) – explicit kontextussal
    (EntityType.DATE_OF_BIRTH, r"(?i)\b(?:született|szül\.?|dob|date of birth)\s*:\s*(?:19|20)\d{2}[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:0[1-9]|[12]\d|3[01])\b", 0.90, RiskClass.DIRECT_PII),
    (EntityType.DATE_OF_BIRTH, r"(?i)\b(?:született|szül\.?|dob|date of birth)\s*:\s*(?:0[1-9]|[12]\d|3[01])[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:19|20)\d{2}\b", 0.90, RiskClass.DIRECT_PII),
    # IP
    (EntityType.IP_ADDRESS, r"\b(?:\d{1,3}\.){3}\d{1,3}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.IP_ADDRESS, r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
    # MAC
    (EntityType.MAC_ADDRESS, r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", 0.88, RiskClass.INDIRECT_IDENTIFIER),
    # IMEI (15 digits, optionally space-separated)
    (EntityType.IMEI, r"\b\d{15}\b", 0.65, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.IMEI, r"(?i)\bIMEI\s*:\s*\d{15}\b", 0.92, RiskClass.INDIRECT_IDENTIFIER),
    # VIN (17 alphanumeric)
    (EntityType.VIN, r"\b[A-HJ-NPR-Z0-9]{17}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.VIN, r"(?i)\bVIN\s*:\s*[A-HJ-NPR-Z0-9]{17}\b", 0.92, RiskClass.INDIRECT_IDENTIFIER),
    # Vehicle registration – HU, ES, generic
    (EntityType.VEHICLE_REGISTRATION, r"\b[A-Z]{3}[- ]?\d{3}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.VEHICLE_REGISTRATION, r"\b[A-Z]{2}[- ]?\d{2}[- ]?[A-Z]{2}[- ]?\d{2}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.VEHICLE_REGISTRATION, r"\b\d{4}\s+[A-Z]{3}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    # Customer ID / Contract / Ticket
    (EntityType.CUSTOMER_ID, r"\b(?:UGY|UGYFEL|CLIENT|cliente|cust)[\- ]?\d{4,10}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CUSTOMER_ID, r"#\d{4,12}\b", 0.60, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CONTRACT_NUMBER, r"\b(?:SZ|Szerz\.?|Szerződés|CONTRACT|contrato)[\- ]?\d{4,12}\b", 0.80, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.TICKET_ID, r"\b(?:TKT|TICKET|JIRA)[\- ]?\d{4,10}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.EMPLOYEE_ID, r"\b(?:EMP|employee|dolgozói|empleado)[\- ]?\d{4,10}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # Session / Cookie / Device
    (EntityType.SESSION_ID, r"\b(?:sess(?:ion)?_?|sessionid)[\w\-]{8,64}\b", 0.72, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DEVICE_ID, r"\b(?:device[_\s]?id|deviceid)[\s:=]\s*[\w\-]{8,40}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # Hungarian address (irányítószám + város + utca + szám)
    (EntityType.POSTAL_ADDRESS, r"\b\d{4}\s+[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+(?:\s+[A-Za-záéíóöüőú]+)*\s*,\s*[A-ZÁÉÍÓÖÜŐÚa-záéíóöüőú][^,]*?\s+\d+[a-z]?\s*\.?", 0.82, RiskClass.DIRECT_PII),
    # Spanish address: Calle/Plaza Name Number, City (e.g. Calle Mayor 12, Madrid)
    (EntityType.POSTAL_ADDRESS, r"\b(?:Calle|Plaza|Callejón|Avenida|Av\.?)\s+[A-Za-záéíóúñÁÉÍÓÚÑ0-9\s]+\d+\.?,?\s+[A-Za-záéíóúñÁÉÍÓÚÑ\s]+", 0.78, RiskClass.DIRECT_PII),
    # Spanish customer/contract labels (plate 1234 ABC already covered by \d{4}\s+[A-Z]{3} above)
    (EntityType.CUSTOMER_ID, r"\b(?:cliente|id\s*cliente|número\s*de\s*cliente)\s*[:\-]?\s*\d{4,12}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CONTRACT_NUMBER, r"\b(?:contrato|número\s*de\s*contrato|contrato\s*n\.?º?)\s*[:\-]?\s*\d{4,12}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # TAJ (Hungarian personal id) – 9 digits in 3-3-3
    (EntityType.PERSONAL_ID, r"\b\d{3}\s?\d{3}\s?\d{3}\b", 0.65, RiskClass.DIRECT_PII),
    (EntityType.TAX_ID, r"\b\d{8}[\- ]?\d{1}[\- ]?\d{2}\b", 0.72, RiskClass.DIRECT_PII),
    # Passport / Driver license – generic patterns
    (EntityType.PASSPORT_NUMBER, r"(?i)\b(?:passport|útlevél|pasaporte)\s*:\s*[A-Z0-9]{6,12}\b", 0.85, RiskClass.DIRECT_PII),
    (EntityType.DRIVER_LICENSE_NUMBER, r"(?i)\b(?:driver|jogosítvány|permiso)\s*(?:license|number|szám|número)?\s*:\s*[A-Z0-9]{6,12}\b", 0.82, RiskClass.DIRECT_PII),
]


class RegexDetector(BaseDetector):
    """Detector using predefined regex rules. No external models required."""

    name = "regex"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for entity_type, pattern, confidence, risk in _REGEX_RULES:
            try:
                for m in re.finditer(pattern, text):
                    start, end = m.start(), m.end()
                    matched = m.group(0).strip()
                    if not matched:
                        continue
                    action = RecommendedAction.MASK if confidence >= 0.85 else RecommendedAction.REVIEW_REQUIRED
                    results.append(
                        DetectionResult(
                            entity_type=entity_type,
                            matched_text=matched,
                            start=start,
                            end=end,
                            language=language,
                            source_detector=self.name,
                            confidence_score=confidence,
                            risk_level=risk,
                            recommended_action=action,
                        )
                    )
            except re.error:
                continue
        return results
