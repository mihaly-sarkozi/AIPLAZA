# PII layer: single source of truth

## Current state

- **Single implementation:** `apps.knowledge.pii_gdpr` — all detection, policy, and sanitization logic. One engine, no duplicate code.
- **Legacy API:** `apps.knowledge.pii` is a **thin compatibility adapter** only. It does not implement detection.

## What lives where

| Responsibility | Location |
|----------------|----------|
| Detection (regex, NER, email classifier, vehicle, technical IDs, …) | `pii_gdpr` (detectors, MultilingualAnalyzer) |
| Policy (MASK/KEEP/review, sensitivity scope) | `pii_gdpr` (PolicyEngine, PolicyConfig) |
| Sanitization (placeholders, redaction) | `pii_gdpr` (Sanitizer) + `pii.sanitization` (legacy placeholder map & replacement) |
| Public API `filter_pii(text, sensitivity)` | `pii.adapter.filter_pii_via_gdpr` → runs pii_gdpr pipeline, maps to legacy `PiiMatch` |
| Public API `apply_pii_replacements(...)` | `pii.sanitization` (unchanged) |
| Sensitivity sets (weak/medium/strong) | `pii.entities` + `pii.policy.entities_for_sensitivity` (used by pii_gdpr pipeline and adapter) |
| Exception `PiiConfirmationRequiredError` | `pii.policy` (legacy type strings in `detected_types`) |

## Adapter (`pii.adapter`)

- **filter_pii_via_gdpr(text, sensitivity):** Calls `pii_gdpr.IngestionPipeline.run(text)` with `PolicyConfig(sensitivity=sensitivity)`. Converts each `DetectionResult` to legacy `(start, end, legacy_type_str, value)` via `legacy_mapping.get_legacy_name`. Returns `List[PiiMatch]`. No fallback; on failure the caller gets an exception or empty list depending on where it’s called.

## Deprecated / unused

- **`pii.nlp_setup`**, **`pii.recognizers`**: Removed. Detection is only in pii_gdpr.
- **`pii.pipeline`**: No detection logic; only delegates to the adapter and to `pii.sanitization` for replacements.

## Adding new PII types

1. Add the detector and `EntityType` in **pii_gdpr**.
2. Add the mapping in **`pii_gdpr/policy/legacy_mapping.py`** (EntityType → legacy name).
3. If the legacy name should appear in weak/medium/strong scope, add it to **`pii.entities`** (WEAK_ENTITIES, MEDIUM_ENTITIES, STRONG_ENTITIES).
4. Add placeholder/generalization in **`pii.sanitization`** (LEGACY_TO_STANDARD_PLACEHOLDER, LEGACY_TO_GENERALIZATION) if needed.

Do not add detection or policy logic in `pii`; only in `pii_gdpr`.
