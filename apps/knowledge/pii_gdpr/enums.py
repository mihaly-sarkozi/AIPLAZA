# apps/knowledge/pii_gdpr/enums.py
"""
Enumerations for PII/GDPR detection and sanitization pipeline.
Operational categories and recommended actions; no legal determination.
"""
from __future__ import annotations

from enum import Enum


class RiskClass(str, Enum):
    """Operational risk classification of a detection (not a legal determination)."""

    DIRECT_PII = "DIRECT_PII"
    INDIRECT_IDENTIFIER = "INDIRECT_IDENTIFIER"
    SENSITIVE_DATA = "SENSITIVE_DATA"
    LOW_RISK_ORG_DATA = "LOW_RISK_ORG_DATA"
    UNCERTAIN = "UNCERTAIN"


class RecommendedAction(str, Enum):
    """Recommended handling for a detection or document."""

    MASK = "MASK"
    GENERALIZE = "GENERALIZE"
    KEEP = "KEEP"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECT_DOCUMENT = "REJECT_DOCUMENT"
    IGNORE = "IGNORE"


class EntityType(str, Enum):
    """Entity types detected by the pipeline."""

    # Direct identifiers
    PERSON_NAME = "PERSON_NAME"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    POSTAL_ADDRESS = "POSTAL_ADDRESS"
    DATE = "DATE"  # általános dátum (nem feltétlenül születési)
    DATE_OF_BIRTH = "DATE_OF_BIRTH"  # születési dátum (kontextus: Született:, dob:, date of birth)
    PERSONAL_ID = "PERSONAL_ID"
    TAX_ID = "TAX_ID"
    PASSPORT_NUMBER = "PASSPORT_NUMBER"
    DRIVER_LICENSE_NUMBER = "DRIVER_LICENSE_NUMBER"
    # Financial
    IBAN = "IBAN"
    BANK_ACCOUNT_NUMBER = "BANK_ACCOUNT_NUMBER"
    PAYMENT_CARD_NUMBER = "PAYMENT_CARD_NUMBER"
    # Online / technical
    IP_ADDRESS = "IP_ADDRESS"
    MAC_ADDRESS = "MAC_ADDRESS"
    IMEI = "IMEI"
    DEVICE_ID = "DEVICE_ID"
    USER_ID = "USER_ID"
    SESSION_ID = "SESSION_ID"
    COOKIE_ID = "COOKIE_ID"
    # Vehicle
    VEHICLE_REGISTRATION = "VEHICLE_REGISTRATION"
    VIN = "VIN"
    ENGINE_IDENTIFIER = "ENGINE_IDENTIFIER"
    CHASSIS_IDENTIFIER = "CHASSIS_IDENTIFIER"
    # Document / business
    CUSTOMER_ID = "CUSTOMER_ID"
    CONTRACT_NUMBER = "CONTRACT_NUMBER"
    TICKET_ID = "TICKET_ID"
    EMPLOYEE_ID = "EMPLOYEE_ID"
    # Sensitive hints (context/keyword)
    HEALTH_DATA_HINT = "HEALTH_DATA_HINT"
    BIOMETRIC_HINT = "BIOMETRIC_HINT"
    POLITICAL_OPINION_HINT = "POLITICAL_OPINION_HINT"
    RELIGION_HINT = "RELIGION_HINT"
    UNION_MEMBERSHIP_HINT = "UNION_MEMBERSHIP_HINT"
    SEXUAL_ORIENTATION_HINT = "SEXUAL_ORIENTATION_HINT"
    # Fallback
    UNKNOWN = "UNKNOWN"


class EmailClassification(str, Enum):
    """Email address classification for policy decisions."""

    PERSONAL_FREE_PROVIDER = "personal_free_provider"
    ORGANIZATIONAL_PERSONAL = "organizational_personal"
    ROLE_BASED_ORGANIZATIONAL = "role_based_organizational"
    UNKNOWN = "unknown"


class PolicyMode(str, Enum):
    """Policy strictness mode."""

    STRICT = "strict"
    BALANCED = "balanced"
    PERMISSIVE = "permissive"


class Language(str, Enum):
    """Supported languages."""

    EN = "en"
    HU = "hu"
    ES = "es"
    UNKNOWN = "unknown"
