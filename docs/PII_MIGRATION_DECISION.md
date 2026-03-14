# PII Migration Decision: Single Source of Truth

## Decision: Option B — `pii_gdpr` as main, `pii` as compatibility wrapper

**Chosen approach:** Make **`apps.knowledge.pii_gdpr`** the single source of truth for PII detection and sanitization. Keep **`apps.knowledge.pii`** only as a **thin adapter** that exposes the legacy API (`filter_pii`, `apply_pii_replacements`, `PiiConfirmationRequiredError`) by delegating to `pii_gdpr` and converting results to the existing contract.

This removes duplicate logic and ensures one implementation path: all detection and policy logic lives in `pii_gdpr`; `pii` is a facade for backward compatibility with the knowledge-base ingest flow.

---

## What stays

| Item | Location | Role |
|------|----------|------|
| **Public API** | `apps.knowledge.pii` | `filter_pii(text, sensitivity) -> List[PiiMatch]`, `apply_pii_replacements(text, matches, ref_ids) -> str`, `PiiMatch`, `PiiConfirmationRequiredError`. Unchanged signatures and behavior for callers. |
| **Application import** | `apps.knowledge.application.pii_filter` | Continues to import from `apps.knowledge.pii`; no change for `knowledge_service` or router. |
| **KB ingest flow** | `knowledge_service.add_block`, `train_from_file` | Still use `filter_pii`, `apply_pii_replacements`, `PiiConfirmationRequiredError`; no code change. |
| **Exception** | `PiiConfirmationRequiredError` | Remains in `pii.policy` (or re-exported from `pii`); `detected_types` remains a list of **legacy type strings** (e.g. `"email"`, `"név"`). |
| **Storage contract** | `add_personal_data(kb_id, data_type, extracted_value)` | `data_type` remains the **legacy type string** (email, telefonszám, név, cím, dátum, iban, rendszám, ügyfélazonosító, szerződésszám, ticket_id, and any new types we add as snake_case). |

---

## What becomes the implementation (source of truth)

| Item | Location | Role |
|------|----------|------|
| **All detection logic** | `apps.knowledge.pii_gdpr` | Regex, NER, context, email classifier, vehicle, technical detectors; merge/dedupe; policy engine; sanitizer. |
| **Pipeline** | `pii_gdpr.pipeline.IngestionPipeline` | Single entry for “run full pipeline”. |
| **Entity types** | `pii_gdpr.enums.EntityType` | Canonical list of entity types. |
| **Tests** | `tests/test_pii_gdpr_*.py` | Unit and integration tests for detectors, pipeline, sanitizer, email classifier. |

---

## What is deprecated (do not extend)

| Item | Location | Note |
|------|----------|------|
| **Legacy pipeline implementation** | **REMOVED** | `pii.pipeline` now only delegates to the adapter; no regex/NER/Presidio code. |
| **Legacy policy implementation** | `apps.knowledge.pii.policy` | `filter_by_policy`, `entities_for_sensitivity`, and the old WEAK/MEDIUM/STRONG sets are **deprecated** for use inside the pipeline. They remain only for: (1) adapter’s sensitivity → allowed legacy types, and (2) `PiiConfirmationRequiredError`. Policy logic for “what to detect” lives in `pii_gdpr`. |
| **Legacy NLP/Presidio** | `apps.knowledge.pii.nlp_setup`, `recognizers` | **Deprecated, unused.** Detection is only in `pii_gdpr`. Can be deleted in a future cleanup. |

Deprecated code is kept only so that the adapter can:
- Map **sensitivity** (weak/medium/strong) to the set of **legacy type names** allowed in the adapter output (`entities_for_sensitivity`).
- Re-export **PiiConfirmationRequiredError** and use legacy type names in `detected_types`.

No new features should be added to the deprecated pipeline or policy logic.

---

## What will be removed later (optional cleanup)

| Item | When / condition |
|------|-------------------|
| **Legacy regex/patterns in `pii.pipeline`** | After the adapter is stable and all tests (including `test_pii_pipeline.py`) pass via the adapter. Then `_filter_pii_legacy`, `_LEGACY_PATTERNS`, and the Presidio branch in `pii.pipeline` can be removed; `filter_pii` will only call the adapter. |
| **Presidio/NER in `pii`** | When removal of legacy pipeline happens; `pii.nlp_setup` and `pii.recognizers` can be deleted if nothing else uses them. |
| **Duplicate tests** | Tests in `tests/test_pii_pipeline.py` that duplicate `test_pii_gdpr_*` can be migrated to run against the adapter (same contract) or removed in favor of `test_pii_gdpr_*` plus one adapter test. |

---

## Adapter behavior

The **adapter** (`pii.adapter` or implemented inside `pii.pipeline`):

1. **filter_pii(text, sensitivity)**  
   - Calls `pii_gdpr` (e.g. `IngestionPipeline.run(text)`).  
   - Maps each `DetectionResult.entity_type` to a **legacy type string** (see table below).  
   - Filters to only those whose legacy type is in `entities_for_sensitivity(sensitivity)`.  
   - Returns `List[PiiMatch]` where `PiiMatch = (start, end, legacy_type_str, value)`.  
   - Deduplicates overlapping spans (e.g. keep higher confidence) and sorts by start.

2. **apply_pii_replacements(text, matches, ref_id_by_index)**  
   - Unchanged: replace each `(start, end, dtype, _)` with `[dtype_ref_id]` from end to start.

3. **PiiConfirmationRequiredError**  
   - Still raised with `detected_types: List[str]` = list of **legacy type strings** (e.g. `["email", "név"]`).

### Entity type → legacy type (adapter)

| EntityType (pii_gdpr) | Legacy type string |
|------------------------|---------------------|
| PERSON_NAME | név |
| EMAIL_ADDRESS | email |
| PHONE_NUMBER | telefonszám |
| POSTAL_ADDRESS | cím |
| DATE_OF_BIRTH | dátum |
| IBAN | iban |
| BANK_ACCOUNT_NUMBER | bankszámla |
| PAYMENT_CARD_NUMBER | kártyaszám |
| VEHICLE_REGISTRATION | rendszám |
| VIN | vin |
| ENGINE_IDENTIFIER | motorszám |
| CUSTOMER_ID | ügyfélazonosító |
| CONTRACT_NUMBER | szerződésszám |
| TICKET_ID | ticket_id |
| EMPLOYEE_ID | munkavállalói_azonosító |
| IP_ADDRESS | ip_cím |
| MAC_ADDRESS | mac_cím |
| IMEI | imei |
| SESSION_ID | session_id |
| PERSONAL_ID | személyi_azonosító |
| TAX_ID | adóazonosító |
| PASSPORT_NUMBER | útlevél |
| DRIVER_LICENSE_NUMBER | jogosítvány |
| (sensitive hints) | health_hint, biometric_hint, … (optional) |
| UNKNOWN (from NER) | szervezet or hely only if we later add NER output for ORG/LOC; else skip |

For any `EntityType` not in the table, the adapter can use `entity_type.value.lower()` or skip. New legacy types (e.g. `bankszámla`, `vin`) can be added to `MEDIUM_ENTITIES` or `STRONG_ENTITIES` in `pii.policy` so they appear when sensitivity allows.

---

## Tests

- **Primary tests** for detection, policy, sanitizer, and pipeline: **`tests/test_pii_gdpr_*.py`**. These are the source of truth for behavior.
- **Adapter / backward compatibility:** Add (or keep) tests that call `filter_pii` and `apply_pii_replacements` from `pii` with the same contract (e.g. sensitivity weak/medium/strong, expected legacy types, confirm flow). These tests ensure the KB ingest path still works.
- **Legacy `test_pii_pipeline.py`:** Can be kept as integration tests for the **adapter** (same public API), or gradually migrated to `test_pii_gdpr_*` plus one adapter test suite.

---

## Implementation status (current)

- **Single implementation:** All detection runs in `pii_gdpr` (IngestionPipeline, detectors, policy engine, sanitizer). No competing implementation in `pii`.
- **Adapter:** `apps.knowledge.pii.adapter` — `filter_pii_via_gdpr(text, sensitivity)` runs `pii_gdpr.IngestionPipeline`, maps `EntityType` → legacy type (via `legacy_mapping.get_legacy_name`), filters by `entities_for_sensitivity(sensitivity)`; returns `List[PiiMatch]`. No fallback.
- **Pipeline:** `apps.knowledge.pii.pipeline.filter_pii` only calls the adapter; on exception returns `[]`. No legacy regex/NER.
- **Application:** `pii_filter.filter_pii` uses the adapter only; no legacy fallback.
- **Policy (thin):** `pii.policy.entities_for_sensitivity` and `PiiConfirmationRequiredError`; sensitivity sets live in `pii.entities`. The pii_gdpr pipeline uses `entities_for_sensitivity` when `PolicyConfig.sensitivity` is set.

---

## Summary

- **Single source of truth:** `apps.knowledge.pii_gdpr` — all detection and policy logic.
- **Compatibility layer:** `apps.knowledge.pii` — only `filter_pii`, `apply_pii_replacements`, `PiiMatch`, `PiiConfirmationRequiredError`, implemented by delegating to `pii_gdpr` and mapping to legacy types.
- **No new logic in `pii`;** no duplicate detectors or patterns. New features go into `pii_gdpr` only.
