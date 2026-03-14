# PII/GDPR Pipeline — Definition of Done

This document locks down what **“done”** means for the PII/GDPR detection and sanitization pipeline. It defines the official supported entity list, implementation status per entity, and success criteria that must be met before the pipeline is considered complete.

---

## 1. Scope: Two Pipelines

The project has two PII-related implementations:

| Layer | Location | Role |
|-------|----------|------|
| **Legacy / KB ingest** | `apps/knowledge/pii/` | Used by knowledge base training today. Sensitivity-based policy (weak/medium/strong). Returns `(start, end, data_type, value)` and supports confirm flow. |
| **GDPR / full pipeline** | `apps/knowledge/pii_gdpr/` | Target state: layered detectors, policy engine, sanitizer, structured output. Not yet wired into KB ingest. |

**Definition of done** applies to the **target state**: the pipeline that will back KB ingest (either by evolving the legacy `pii` to match this spec, or by switching ingest to `pii_gdpr` and aligning behavior). The legacy `pii` entity names (e.g. `email`, `telefonszám`, `név`, `cím`) map to the official entity list below where relevant.

---

## 2. Official Supported Entity List

The following entity types are the **official supported list** for the PII/GDPR pipeline. Any entity not in this list is out of scope for “done” unless explicitly added later.

### 2.1 Direct identifiers

| Entity type | Description | Status (see §3) |
|-------------|-------------|------------------|
| `PERSON_NAME` | Full name, e.g. “Kovács Anna”, “John Smith” | Implemented |
| `EMAIL_ADDRESS` | Email (with classification: personal / org personal / role-based) | Implemented |
| `PHONE_NUMBER` | Phone (HU, ES, international formats) | Implemented |
| `POSTAL_ADDRESS` | Structured address (e.g. HU: irányítószám + város + utca + szám) | Implemented |
| `DATE_OF_BIRTH` | Birth date (ISO, EU, HU space-sep, “született:” / “dob:” context) | Implemented |
| `PERSONAL_ID` | National personal ID (e.g. TAJ-style patterns) | Partially implemented |
| `TAX_ID` | Tax identifier (e.g. HU 8-1-2) | Partially implemented |
| `PASSPORT_NUMBER` | Passport number (label + pattern) | Partially implemented |
| `DRIVER_LICENSE_NUMBER` | Driver license number (label + pattern) | Partially implemented |

### 2.2 Financial

| Entity type | Description | Status |
|-------------|-------------|--------|
| `IBAN` | IBAN format | Implemented |
| `BANK_ACCOUNT_NUMBER` | Bank account (e.g. HU 8-8-8) | Implemented |
| `PAYMENT_CARD_NUMBER` | Card number (4×4 digits) | Implemented |

### 2.3 Online / technical identifiers

| Entity type | Description | Status |
|-------------|-------------|--------|
| `IP_ADDRESS` | IPv4, IPv6 | Implemented |
| `MAC_ADDRESS` | MAC (e.g. 00:1A:2B:3C:4D:5E) | Implemented |
| `IMEI` | IMEI 15 digits (with/without “IMEI:” label) | Implemented |
| `DEVICE_ID` | Device ID (pattern + context) | Partially implemented |
| `USER_ID` | User identifier (e.g. CRM user ID) | Planned / not implemented |
| `SESSION_ID` | Session ID (e.g. sess_xxx) | Implemented |
| `COOKIE_ID` | Cookie identifier | Planned / not implemented |

### 2.4 Vehicle-related

| Entity type | Description | Status |
|-------------|-------------|--------|
| `VEHICLE_REGISTRATION` | License plate (HU, ES, generic) | Implemented |
| `VIN` | 17-char VIN (with/without label) | Implemented |
| `ENGINE_IDENTIFIER` | Engine number (context: motorszám / engine number) | Implemented |
| `CHASSIS_IDENTIFIER` | Chassis number (context: alvázszám / chassis) | Partially implemented |

### 2.5 Document / business identifiers

| Entity type | Description | Status |
|-------------|-------------|--------|
| `CUSTOMER_ID` | Customer ID (UGY-, CLIENT-, #xxxx) | Implemented |
| `CONTRACT_NUMBER` | Contract number (SZ-, Szerződés-, CONTRACT-) | Implemented |
| `TICKET_ID` | Ticket/incident ID (TKT-, JIRA-) | Implemented |
| `EMPLOYEE_ID` | Employee ID (EMP-, employee-) | Implemented |

### 2.6 Sensitive categories (hints only)

| Entity type | Description | Status |
|-------------|-------------|--------|
| `HEALTH_DATA_HINT` | Keyword/context hint (e.g. cukorbeteg, surgery, lab) | Implemented |
| `BIOMETRIC_HINT` | Keyword hint (biometric, fingerprint) | Implemented |
| `POLITICAL_OPINION_HINT` | Keyword hint (political, vote) | Implemented |
| `RELIGION_HINT` | Keyword hint (religion, church) | Implemented |
| `UNION_MEMBERSHIP_HINT` | Keyword hint (union, szakszervezet) | Implemented |
| `SEXUAL_ORIENTATION_HINT` | Keyword hint (orientation) | Implemented |

### 2.7 Unsupported / out of scope for “done”

- **USER_ID**, **COOKIE_ID**: planned; no detector or tests required for done.
- **CHASSIS_IDENTIFIER**: partially implemented (context detector); full pattern+context as for engine is optional for done.
- Entities not listed in §2 are **not implemented** and must be explicitly marked as such in code or tests (e.g. “NOT_IMPLEMENTED” or skipped tests with reason).

---

## 3. Implementation Status (per entity)

### Implemented

- **At least one detector** (regex and/or NER and/or dedicated detector) emits the entity.
- **Policy** maps the entity to a risk class and recommended action.
- **Sanitizer** can MASK or GENERALIZE it.
- **Tests**: at least one **positive** test (sample text that must be detected) and, where feasible, one **negative** test (text that must not be detected as that entity).

**List:** PERSON_NAME, EMAIL_ADDRESS, PHONE_NUMBER, POSTAL_ADDRESS, DATE_OF_BIRTH, IBAN, BANK_ACCOUNT_NUMBER, PAYMENT_CARD_NUMBER, IP_ADDRESS, MAC_ADDRESS, IMEI, SESSION_ID, VEHICLE_REGISTRATION, VIN, ENGINE_IDENTIFIER, CUSTOMER_ID, CONTRACT_NUMBER, TICKET_ID, EMPLOYEE_ID, and all six sensitive hints.

### Partially implemented

- Detector exists but is **pattern-only** (no or weak context), or **coverage is limited** (e.g. one country/format), or **no negative test** yet.
- Documented in this file and, if applicable, in code (e.g. “PARTIALLY_IMPLEMENTED” or comment).

**List:** PERSONAL_ID, TAX_ID, PASSPORT_NUMBER, DRIVER_LICENSE_NUMBER, DEVICE_ID, CHASSIS_IDENTIFIER.

### Planned / not implemented

- In the official entity list but **no detector** (or only a stub).
- Must be **explicitly marked** in code/tests (e.g. skipped test with `@pytest.mark.skip(reason="ENTITY_X not implemented")` or constant `NOT_IMPLEMENTED_ENTITIES`).

**List:** USER_ID, COOKIE_ID.

---

## 4. Success Criteria (checklist for “done”)

All of the following must be true.

### 4.1 Detectors

- [ ] **Every supported entity** in the “Implemented” list has **at least one detector** that can emit it (regex, NER, or dedicated detector).
- [ ] **Partially implemented** entities have at least one detector; gaps (e.g. context, formats) are documented in this file or in code.
- [ ] **Planned / not implemented** entities are listed in §2.7 and §3 and are not required to have a detector for “done”.

### 4.2 Tests

- [ ] **Every implemented entity** has:
  - at least one **positive** test (input text that must produce at least one detection of that entity), and
  - where feasible, at least one **negative** test (input that must not be misclassified as that entity).
- [ ] **Unsupported / not implemented** entities are **explicitly marked** (e.g. skipped test with reason, or test that asserts “no detection” for that type in a given string).
- [ ] **Overlapping detections** are tested (merge/dedupe keeps higher confidence or expected span).
- [ ] **Sanitizer** is tested: MASK and, if used, GENERALIZE produce expected output and replacement list; offsets/replacements are consistent.

### 4.3 Pipeline and policy

- [ ] **End-to-end pipeline** runs: raw text → language detection → detectors → merge/dedupe → policy → sanitizer → output (raw detections, policy decisions, sanitized text, summary).
- [ ] **Policy** supports configurable modes (e.g. strict / balanced / permissive) and, for email, organizational vs role-based allow/deny.
- [ ] **Thresholds** (e.g. mask ≥ 0.85, review ≥ 0.60) are configurable.

### 4.4 File ingest and review flow

- [ ] **File ingest flow** (e.g. PDF/DOCX → extract text → PII detection → store) is **tested end-to-end** (unit or integration test).
- [ ] **Review / confirmation behavior** is tested: when policy or mode requires “review”, the flow returns a clear signal (e.g. “confirmation required” / list of detected types) and, after “confirm”, ingestion proceeds with sanitization (or stored PII refs). Legacy: `PiiConfirmationRequiredError` and `confirm_pii` flag; target pipeline must have an equivalent contract.

### 4.5 Documentation and code

- [ ] **This document** is the single source of truth for “done”; any change to supported entities or status is reflected here.
- [ ] **Code** references this definition where useful (e.g. “See docs/PII_GDPR_DEFINITION_OF_DONE.md” in README or module docstring).
- [ ] **Unsupported** entities are not silently ignored in tests: they are either skipped with reason or asserted as “not implemented”.

---

## 5. Mapping: Legacy `pii` vs Official Entity List

For alignment between the legacy branch and the target state:

| Legacy (`apps/knowledge/pii`) | Official entity (target) |
|-------------------------------|---------------------------|
| email | EMAIL_ADDRESS |
| telefonszám | PHONE_NUMBER |
| iban | IBAN |
| rendszám | VEHICLE_REGISTRATION |
| ügyfélazonosító | CUSTOMER_ID |
| szerződésszám | CONTRACT_NUMBER |
| ticket_id | TICKET_ID |
| dátum | DATE_OF_BIRTH |
| név | PERSON_NAME |
| cím | POSTAL_ADDRESS |
| szervezet, hely | (policy: allow org/location; no separate entity in list above for “done”) |

When migrating ingest to the full pipeline, the legacy sensitivity levels (weak / medium / strong) should map to policy mode and/or entity allowlists so that behavior remains consistent.

---

## 6. Sign-off

“Done” is achieved when:

1. The **official supported entity list** (§2) and **implementation status** (§3) are satisfied.
2. All **success criteria** (§4) are met and checked (e.g. in a PR checklist or CI).
3. **File ingest** and **review/confirmation** behavior are tested end-to-end as in §4.4.
4. **Unsupported** entities are explicitly marked as in §2.7 and §4.2.

Changes to this definition (new entities, status changes, or criteria) require an update to this document and, where applicable, to code and tests.
