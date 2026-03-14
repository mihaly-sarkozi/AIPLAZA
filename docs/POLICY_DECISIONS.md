# PII/GDPR policy engine: decision flow

Reference: `apps.knowledge.pii_gdpr.policy.policy_engine.PolicyEngine`.

## Risk classes

| RiskClass | Meaning | Typical entities |
|-----------|--------|-------------------|
| DIRECT_PII | Direct identifier | PERSON_NAME, EMAIL_ADDRESS, PHONE_NUMBER, POSTAL_ADDRESS, DATE_OF_BIRTH, PERSONAL_ID, TAX_ID, PASSPORT_NUMBER, DRIVER_LICENSE_NUMBER, IBAN, BANK_ACCOUNT_NUMBER, PAYMENT_CARD_NUMBER |
| INDIRECT_IDENTIFIER | Indirect identifier | DATE (generic), IP_ADDRESS, MAC_ADDRESS, IMEI, VEHICLE_*, CUSTOMER_ID, CONTRACT_NUMBER, TICKET_ID, EMPLOYEE_ID, SESSION_ID, DEVICE_ID |
| SENSITIVE_DATA | Sensitive category | HEALTH_DATA_HINT, BIOMETRIC_HINT, POLITICAL_OPINION_HINT, RELIGION_HINT, UNION_MEMBERSHIP_HINT, SEXUAL_ORIENTATION_HINT |
| LOW_RISK_ORG_DATA | Low-risk org data | Allowlisted only |
| UNCERTAIN | Unknown / fallback | UNKNOWN, or not in map |

## Default actions by mode

| Mode | DIRECT_PII | INDIRECT_IDENTIFIER | SENSITIVE_DATA | LOW_RISK_ORG | UNCERTAIN |
|------|------------|---------------------|----------------|--------------|-----------|
| strict | MASK | MASK | REVIEW_REQUIRED | GENERALIZE | REVIEW_REQUIRED |
| balanced | MASK | REVIEW_REQUIRED | REVIEW_REQUIRED | KEEP | REVIEW_REQUIRED |
| permissive | REVIEW_REQUIRED | KEEP | REVIEW_REQUIRED | KEEP | KEEP |

## Recommended actions

- **MASK**: Replace with placeholder (no PII in output).
- **GENERALIZE**: Replace with generic label (e.g. "contact person", "specific date").
- **KEEP**: Do not mask (e.g. allowlisted or low risk).
- **REVIEW_REQUIRED**: Do not auto-mask; require human review / confirm flow.
- **REJECT_DOCUMENT**: Reject the whole document (configurable).
- **IGNORE**: Do not treat as PII for action (e.g. already handled elsewhere).

## Special handling

### Date vs DATE_OF_BIRTH

- **DATE**: Generic date → INDIRECT_IDENTIFIER. If `config.allow_dates` is True → KEEP.
- **DATE_OF_BIRTH**: Direct PII → DIRECT_PII → MASK (unless allow_dates covers it; typically DOB is not allowed). Do not map every date to DATE_OF_BIRTH; only context-based DOB (e.g. "Született:", "dob:").

### Email

- **Role-based** (info@, support@, …): `config.email_role_based_action` (default KEEP).
- **Organizational personal** (név@ceg.hu): `config.email_organizational_personal_action` (default REVIEW).
- **Personal free** (e.g. gmail): DIRECT_PII → MASK in balanced/strict.
- Controlled by `allow_role_based_emails`, `allow_organizational_emails`, and email classifier result.

### Location / organization

- **allow_organization_names**, **allow_locations**: if True, org/location can get KEEP or lower risk; otherwise REVIEW or MASK depending on mode.
- NER-derived ORG/LOC are mapped to UNKNOWN or future ORG_NAME/LOCATION; policy can treat them as LOW_RISK_ORG_DATA or REVIEW.

## Overrides

- **entity_to_risk_map**: Override default entity → risk.
- **risk_to_action_map**: Override default risk → action.
- **allowlist_entities**: Entity type name → LOW_RISK_ORG_DATA.
- **denylist_entities**: Entity type name → DIRECT_PII.

All of the above make policy decisions explicit and easy to reason about; new behavior should be added via config or new risk/action, not ad-hoc branches.
