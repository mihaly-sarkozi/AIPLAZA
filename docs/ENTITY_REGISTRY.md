# PII/GDPR Entity Registry

Single source of truth: `apps.knowledge.pii_gdpr.entity_registry`. Policy, sanitizer, adapter, and `pii.entities` derive from it.

## Status

| Status | Meaning |
|--------|--------|
| **IMPLEMENTED** | Detector in pipeline; policy and sanitizer handle it; safe to use in scope. |
| **PARTIALLY_IMPLEMENTED** | Detector exists but format/language/context limited or ambiguous. |
| **NOT_IMPLEMENTED** | No detector or placeholder only; do not rely. |

## DATE vs DATE_OF_BIRTH

- **DATE**: Generic date (ISO, EU, NER "DATE"). Do **not** treat as date of birth.
- **DATE_OF_BIRTH**: Only when context indicates DOB (e.g. "Született:", "dob:", "date of birth").

Do not map every date to DATE_OF_BIRTH.

## Entity list (from registry)

| EntityType | Legacy name | Status | Sensitivity | Note |
|------------|-------------|--------|-------------|------|
| PERSON_NAME | név | IMPLEMENTED | medium, strong | NER + optional context |
| EMAIL_ADDRESS | email | IMPLEMENTED | weak, medium, strong | Regex + email classifier |
| PHONE_NUMBER | telefonszám | IMPLEMENTED | weak, medium, strong | Regex HU/ES/international |
| POSTAL_ADDRESS | cím | PARTIALLY_IMPLEMENTED | medium, strong | Regex HU/ES; NER LOC may add |
| DATE | dátum | IMPLEMENTED | medium, strong | Generic date only |
| DATE_OF_BIRTH | születési_dátum | IMPLEMENTED | medium, strong | Context: Született:, dob: |
| PERSONAL_ID | személyi_azonosító | PARTIALLY_IMPLEMENTED | medium, strong | e.g. TAJ-like; country-specific |
| TAX_ID | adóazonosító | PARTIALLY_IMPLEMENTED | medium, strong | Format varies by country |
| PASSPORT_NUMBER | útlevél | PARTIALLY_IMPLEMENTED | medium, strong | With context label |
| DRIVER_LICENSE_NUMBER | jogosítvány | PARTIALLY_IMPLEMENTED | medium, strong | With context label |
| IBAN | iban | IMPLEMENTED | medium, strong | Regex |
| BANK_ACCOUNT_NUMBER | bankszámla | IMPLEMENTED | medium, strong | Regex + recognizer |
| PAYMENT_CARD_NUMBER | kártyaszám | IMPLEMENTED | medium, strong | Regex 4x4; may false-positive |
| IP_ADDRESS | ip_cím | IMPLEMENTED | medium, strong | IPv4/IPv6 + technical detector |
| MAC_ADDRESS | mac_cím | IMPLEMENTED | medium, strong | Regex + mac_recognizer |
| IMEI | imei | IMPLEMENTED | medium, strong | 15 digits + imei_recognizer |
| DEVICE_ID | device_id | PARTIALLY_IMPLEMENTED | medium, strong | Regex pattern |
| SESSION_ID | session_id | PARTIALLY_IMPLEMENTED | medium, strong | Regex + technical detector |
| USER_ID | — | NOT_IMPLEMENTED | — | No detector |
| COOKIE_ID | — | NOT_IMPLEMENTED | — | No detector |
| VEHICLE_REGISTRATION | rendszám | IMPLEMENTED | medium, strong | Regex HU/ES + vehicle_detector |
| VIN | vin | IMPLEMENTED | medium, strong | 17-char + recognizers |
| ENGINE_IDENTIFIER | motorszám | IMPLEMENTED | medium, strong | engine_id + vehicle_detector |
| CHASSIS_IDENTIFIER | alvázszám | IMPLEMENTED | medium, strong | engine_id + vehicle_detector |
| CUSTOMER_ID | ügyfélazonosító | IMPLEMENTED | medium, strong | Regex HU/ES + context |
| CONTRACT_NUMBER | szerződésszám | IMPLEMENTED | medium, strong | Regex HU/ES |
| TICKET_ID | ticket_id | IMPLEMENTED | medium, strong | Regex TKT/JIRA |
| EMPLOYEE_ID | munkavállalói_azonosító | IMPLEMENTED | medium, strong | Regex EMP/employee/… |
| HEALTH_DATA_HINT | health_hint | PARTIALLY_IMPLEMENTED | — | Context/keyword only |
| BIOMETRIC_HINT | biometric_hint | PARTIALLY_IMPLEMENTED | — | Context/keyword only |
| POLITICAL_OPINION_HINT | political_hint | PARTIALLY_IMPLEMENTED | — | Context/keyword only |
| RELIGION_HINT | religion_hint | PARTIALLY_IMPLEMENTED | — | Context/keyword only |
| UNION_MEMBERSHIP_HINT | union_hint | PARTIALLY_IMPLEMENTED | — | Context/keyword only |
| SEXUAL_ORIENTATION_HINT | sexual_orientation_hint | PARTIALLY_IMPLEMENTED | — | Context/keyword only |
| UNKNOWN | — | NOT_IMPLEMENTED | — | NER/fallback |

Strong sensitivity also includes legacy **szervezet** (org) and **hely** (location) for NER-derived types.

## Alignment

- **policy**: `entities_for_sensitivity(sensitivity)` → `entity_registry.get_sensitivity_set(sensitivity)`.
- **pii.entities**: WEAK/MEDIUM/STRONG and IMPLEMENTED/PARTIAL/NOT_YET sets built from registry.
- **legacy_mapping**: ENTITY_TYPE_TO_LEGACY built from ENTITY_REGISTRY.
- **sanitizer** (pii_gdpr + pii): placeholder/generalization maps must include all legacy names used by registry.
