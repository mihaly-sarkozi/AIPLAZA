# apps/knowledge/pii_gdpr/entity_registry.py
"""
Single source of truth for PII/GDPR entity definitions and implementation status.

Every entity is classified as:
- IMPLEMENTED: detector exists and is used in pipeline; policy and sanitizer handle it.
- PARTIALLY_IMPLEMENTED: detector exists but format/language/context limited; or ambiguous.
- NOT_IMPLEMENTED: no detector or placeholder only; do not rely in production.

DATE vs DATE_OF_BIRTH:
- DATE: generic date (ISO, EU format, or NER "DATE"); not assumed to be DOB.
- DATE_OF_BIRTH: only when context indicates DOB (e.g. "Született:", "dob:", "date of birth").
Do not map every date to DATE_OF_BIRTH.

This module is the canonical reference. Policy, sanitizer, legacy_mapping, pii.entities,
and tests must stay aligned with this registry.
"""
from __future__ import annotations

from enum import Enum
from typing import FrozenSet

from apps.knowledge.pii_gdpr.enums import EntityType


class ImplementationStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIALLY_IMPLEMENTED = "PARTIALLY_IMPLEMENTED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


# (EntityType, status, legacy_name, sensitivity: "weak" | "medium" | "strong" set, note)
# sensitivity: which sensitivity levels include this entity in scope (pii.entities WEAK/MEDIUM/STRONG)
ENTITY_REGISTRY: list[tuple[EntityType, ImplementationStatus, str, FrozenSet[str], str]] = [
    # ---- Direct PII ----
    (EntityType.PERSON_NAME, ImplementationStatus.IMPLEMENTED, "név", frozenset({"medium", "strong"}), "NER + optional context"),
    (EntityType.EMAIL_ADDRESS, ImplementationStatus.IMPLEMENTED, "email", frozenset({"weak", "medium", "strong"}), "Regex + email classifier (role/organizational)"),
    (EntityType.PHONE_NUMBER, ImplementationStatus.IMPLEMENTED, "telefonszám", frozenset({"weak", "medium", "strong"}), "Regex HU/ES/international"),
    (EntityType.POSTAL_ADDRESS, ImplementationStatus.PARTIALLY_IMPLEMENTED, "cím", frozenset({"medium", "strong"}), "Regex HU/ES patterns; NER LOC may add"),
    (EntityType.DATE, ImplementationStatus.IMPLEMENTED, "dátum", frozenset({"medium", "strong"}), "Generic date only; not DOB"),
    (EntityType.DATE_OF_BIRTH, ImplementationStatus.IMPLEMENTED, "születési_dátum", frozenset({"medium", "strong"}), "Context: Született:, dob:, date of birth"),
    (EntityType.PERSONAL_ID, ImplementationStatus.PARTIALLY_IMPLEMENTED, "személyi_azonosító", frozenset({"medium", "strong"}), "e.g. TAJ-like 9 digits; country-specific"),
    (EntityType.TAX_ID, ImplementationStatus.PARTIALLY_IMPLEMENTED, "adóazonosító", frozenset({"medium", "strong"}), "Format varies by country"),
    (EntityType.PASSPORT_NUMBER, ImplementationStatus.PARTIALLY_IMPLEMENTED, "útlevél", frozenset({"medium", "strong"}), "With context label (passport:, útlevél:)"),
    (EntityType.DRIVER_LICENSE_NUMBER, ImplementationStatus.PARTIALLY_IMPLEMENTED, "jogosítvány", frozenset({"medium", "strong"}), "With context label"),
    # ---- Financial ----
    (EntityType.IBAN, ImplementationStatus.IMPLEMENTED, "iban", frozenset({"medium", "strong"}), "Regex"),
    (EntityType.BANK_ACCOUNT_NUMBER, ImplementationStatus.IMPLEMENTED, "bankszámla", frozenset({"medium", "strong"}), "Regex + bank_account_recognizer"),
    (EntityType.PAYMENT_CARD_NUMBER, ImplementationStatus.IMPLEMENTED, "kártyaszám", frozenset({"medium", "strong"}), "Regex 4x4 digits; may false-positive"),
    # ---- Technical / online ----
    (EntityType.IP_ADDRESS, ImplementationStatus.IMPLEMENTED, "ip_cím", frozenset({"medium", "strong"}), "IPv4/IPv6 + technical_identifier_detector"),
    (EntityType.MAC_ADDRESS, ImplementationStatus.IMPLEMENTED, "mac_cím", frozenset({"medium", "strong"}), "Regex + mac_recognizer"),
    (EntityType.IMEI, ImplementationStatus.IMPLEMENTED, "imei", frozenset({"medium", "strong"}), "15 digits + imei_recognizer"),
    (EntityType.DEVICE_ID, ImplementationStatus.PARTIALLY_IMPLEMENTED, "device_id", frozenset({"medium", "strong"}), "Regex device_id pattern"),
    (EntityType.SESSION_ID, ImplementationStatus.PARTIALLY_IMPLEMENTED, "session_id", frozenset({"medium", "strong"}), "Regex + technical_identifier_detector"),
    (EntityType.USER_ID, ImplementationStatus.PARTIALLY_IMPLEMENTED, "user_id", frozenset({"medium", "strong"}), "Regex: user id, userid, usr_"),
    (EntityType.COOKIE_ID, ImplementationStatus.PARTIALLY_IMPLEMENTED, "cookie_id", frozenset({"medium", "strong"}), "Regex: cookie id, cookieid, ck_"),
    # ---- Vehicle ----
    (EntityType.VEHICLE_REGISTRATION, ImplementationStatus.IMPLEMENTED, "rendszám", frozenset({"medium", "strong"}), "Regex HU/ES + vehicle_detector"),
    (EntityType.VIN, ImplementationStatus.IMPLEMENTED, "vin", frozenset({"medium", "strong"}), "17-char + vin_recognizer, vehicle_detector"),
    (EntityType.ENGINE_IDENTIFIER, ImplementationStatus.IMPLEMENTED, "motorszám", frozenset({"medium", "strong"}), "engine_id_recognizer + vehicle_detector"),
    (EntityType.CHASSIS_IDENTIFIER, ImplementationStatus.IMPLEMENTED, "alvázszám", frozenset({"medium", "strong"}), "engine_id_recognizer + vehicle_detector"),
    # ---- Document / business ----
    (EntityType.CUSTOMER_ID, ImplementationStatus.IMPLEMENTED, "ügyfélazonosító", frozenset({"medium", "strong"}), "Regex HU/ES + context"),
    (EntityType.CONTRACT_NUMBER, ImplementationStatus.IMPLEMENTED, "szerződésszám", frozenset({"medium", "strong"}), "Regex HU/ES"),
    (EntityType.TICKET_ID, ImplementationStatus.IMPLEMENTED, "ticket_id", frozenset({"medium", "strong"}), "Regex TKT/JIRA etc."),
    (EntityType.EMPLOYEE_ID, ImplementationStatus.IMPLEMENTED, "munkavállalói_azonosító", frozenset({"medium", "strong"}), "Regex EMP/employee/dolgozói/empleado"),
    # ---- Sensitive hints (context/keyword only) ----
    (EntityType.HEALTH_DATA_HINT, ImplementationStatus.IMPLEMENTED, "health_hint", frozenset({"medium", "strong"}), "Regex: dátum+orvosi vizsgálat; context keywords"),
    (EntityType.BIOMETRIC_HINT, ImplementationStatus.PARTIALLY_IMPLEMENTED, "biometric_hint", frozenset(), "Context/keyword"),
    (EntityType.POLITICAL_OPINION_HINT, ImplementationStatus.PARTIALLY_IMPLEMENTED, "political_hint", frozenset(), "Context/keyword"),
    (EntityType.RELIGION_HINT, ImplementationStatus.PARTIALLY_IMPLEMENTED, "religion_hint", frozenset(), "Context/keyword"),
    (EntityType.UNION_MEMBERSHIP_HINT, ImplementationStatus.PARTIALLY_IMPLEMENTED, "union_hint", frozenset(), "Context/keyword"),
    (EntityType.SEXUAL_ORIENTATION_HINT, ImplementationStatus.PARTIALLY_IMPLEMENTED, "sexual_orientation_hint", frozenset(), "Context/keyword"),
    # ---- Fallback ----
    (EntityType.UNKNOWN, ImplementationStatus.NOT_IMPLEMENTED, "", frozenset(), "NER/other fallback; not in sensitivity sets"),
]

# NER-only types (no dedicated detector); mapped to legacy "szervezet" / "hely" in some flows
# These are not in EntityType as separate values; NER produces ORG/LOC and we map to UNKNOWN or future ORG_NAME/LOCATION
LEGACY_ORG = "szervezet"
LEGACY_LOCATION = "hely"


def get_implementation_status(entity_type: EntityType) -> ImplementationStatus:
    for et, status, _legacy, _sens, _note in ENTITY_REGISTRY:
        if et == entity_type:
            return status
    return ImplementationStatus.NOT_IMPLEMENTED


def get_legacy_name_from_registry(entity_type: EntityType) -> str:
    """Legacy name for this entity; empty if not in legacy contract."""
    for et, _status, legacy, _sens, _note in ENTITY_REGISTRY:
        if et == entity_type:
            return legacy
    return entity_type.value.lower().replace(" ", "_")


def get_implemented_entity_types() -> frozenset[EntityType]:
    return frozenset(et for et, status, _l, _s, _n in ENTITY_REGISTRY if status == ImplementationStatus.IMPLEMENTED)


def get_partial_entity_types() -> frozenset[EntityType]:
    return frozenset(et for et, status, _l, _s, _n in ENTITY_REGISTRY if status == ImplementationStatus.PARTIALLY_IMPLEMENTED)


def get_sensitivity_set(sensitivity: str) -> frozenset[str]:
    """Return set of legacy names for weak/medium/strong. Single source for pii.policy."""
    s = (sensitivity or "medium").lower()
    result: set[str] = set()
    for _et, _status, legacy, sens, _note in ENTITY_REGISTRY:
        if not legacy:
            continue
        if s == "weak":
            if "weak" in sens:
                result.add(legacy)
        elif s == "medium":
            if "weak" in sens or "medium" in sens:
                result.add(legacy)
        else:  # strong
            if "weak" in sens or "medium" in sens or "strong" in sens:
                result.add(legacy)
    if s == "strong":
        result.add(LEGACY_ORG)
        result.add(LEGACY_LOCATION)
    return frozenset(result)
