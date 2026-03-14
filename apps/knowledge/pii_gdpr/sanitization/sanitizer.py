# apps/knowledge/pii_gdpr/sanitization/sanitizer.py
"""
Sanitizer: replaces or generalizes PII in text according to recommended actions.
Replacement is applied from end to start so offsets remain valid.
"""
from __future__ import annotations

from typing import List, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult, DetectionSummary, SanitizationResult, PolicyDecision


# Placeholder for MASK by entity type
MASK_PLACEHOLDERS: dict[EntityType, str] = {
    EntityType.PERSON_NAME: "[PERSON_NAME]",
    EntityType.EMAIL_ADDRESS: "[EMAIL_ADDRESS]",
    EntityType.PHONE_NUMBER: "[PHONE_NUMBER]",
    EntityType.POSTAL_ADDRESS: "[POSTAL_ADDRESS]",
    EntityType.DATE: "[DATE]",
    EntityType.DATE_OF_BIRTH: "[DATE_OF_BIRTH]",
    EntityType.IBAN: "[IBAN]",
    EntityType.BANK_ACCOUNT_NUMBER: "[BANK_ACCOUNT_NUMBER]",
    EntityType.PAYMENT_CARD_NUMBER: "[PAYMENT_CARD_NUMBER]",
    EntityType.IP_ADDRESS: "[IP_ADDRESS]",
    EntityType.MAC_ADDRESS: "[MAC_ADDRESS]",
    EntityType.IMEI: "[IMEI]",
    EntityType.VIN: "[VIN]",
    EntityType.VEHICLE_REGISTRATION: "[VEHICLE_REGISTRATION]",
    EntityType.ENGINE_IDENTIFIER: "[ENGINE_IDENTIFIER]",
    EntityType.CUSTOMER_ID: "[CUSTOMER_ID]",
    EntityType.CONTRACT_NUMBER: "[CONTRACT_NUMBER]",
    EntityType.TICKET_ID: "[TICKET_ID]",
    EntityType.SESSION_ID: "[SESSION_ID]",
    EntityType.DEVICE_ID: "[DEVICE_ID]",
    EntityType.PERSONAL_ID: "[PERSONAL_ID]",
    EntityType.TAX_ID: "[TAX_ID]",
    EntityType.PASSPORT_NUMBER: "[PASSPORT_NUMBER]",
    EntityType.DRIVER_LICENSE_NUMBER: "[DRIVER_LICENSE_NUMBER]",
    EntityType.EMPLOYEE_ID: "[EMPLOYEE_ID]",
    EntityType.USER_ID: "[USER_ID]",
    EntityType.COOKIE_ID: "[COOKIE_ID]",
    EntityType.CHASSIS_IDENTIFIER: "[CHASSIS_IDENTIFIER]",
}
DEFAULT_PLACEHOLDER = "[PII]"

# Generalization text for GENERALIZE
GENERALIZE_MAP: dict[EntityType, str] = {
    EntityType.PERSON_NAME: "contact person",
    EntityType.POSTAL_ADDRESS: "postal address",
    EntityType.DATE: "specific date",
    EntityType.DATE_OF_BIRTH: "date of birth",
    EntityType.EMAIL_ADDRESS: "[email]",
    EntityType.PHONE_NUMBER: "[phone]",
}


class Sanitizer:
    """Produces sanitized text from raw text, detections, and policy decisions."""

    def __init__(self, mask_placeholders: dict[EntityType, str] | None = None):
        self.mask_placeholders = mask_placeholders or MASK_PLACEHOLDERS

    def _placeholder(self, entity_type: EntityType) -> str:
        return self.mask_placeholders.get(entity_type, f"[{entity_type.value}]")

    def _generalize(self, entity_type: EntityType) -> str:
        return GENERALIZE_MAP.get(entity_type, self._placeholder(entity_type))

    def sanitize(
        self,
        raw_text: str,
        detections: List[DetectionResult],
        decisions: List[PolicyDecision],
        summary: DetectionSummary | None = None,
    ) -> SanitizationResult:
        """
        Apply replacements from end to start so character offsets stay valid.
        Only MASK and GENERALIZE change text; KEEP and REVIEW_REQUIRED leave original (we treat REVIEW as mask for safety).
        """
        if len(detections) != len(decisions):
            decisions = [PolicyDecision(entity_type=d.entity_type, risk_class=d.risk_level, recommended_action=d.recommended_action) for d in detections]
        # Build (start, end, replacement) sorted by start desc so we replace from end
        repl: List[Tuple[int, int, str, str]] = []
        for det, dec in zip(detections, decisions):
            if dec.recommended_action == RecommendedAction.KEEP:
                continue
            if dec.recommended_action == RecommendedAction.MASK or dec.recommended_action == RecommendedAction.REVIEW_REQUIRED:
                replacement = self._placeholder(det.entity_type)
            elif dec.recommended_action == RecommendedAction.GENERALIZE:
                replacement = self._generalize(det.entity_type)
            else:
                continue
            orig = raw_text[det.start:det.end]
            repl.append((det.start, det.end, orig, replacement))
        repl.sort(key=lambda x: -x[0])
        result = raw_text
        for start, end, orig, replacement in repl:
            result = result[:start] + replacement + result[end:]
        return SanitizationResult(
            sanitized_text=result,
            raw_text=raw_text,
            replacements=repl,
            preserved_offsets=True,
            summary=summary,
        )
