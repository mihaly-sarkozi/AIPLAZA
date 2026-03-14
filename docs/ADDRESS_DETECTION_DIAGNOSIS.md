# Address Detection – Diagnosis & Patch Plan

## 1. Diagnosis (Root Cause)

### Problem A: Hungarian addresses not fully extended
- **Root cause**: The span extender had no patterns for `A épület`, `4. emelet`, `2/7. ajtó` (fixed in prior session).
- **Remaining**: Shortened form `Budapest, Keleti Károly 18-24., 2/7.` – `find_address_blocks` requires `_ADDRESS_BLOCK_WORDS` in context; without "utca" the block is skipped.
- **Fix**: Add regex pattern for shortened HU address (City, Name Number, optional suffix). Relax `find_address_blocks` context when comma + capitalized words precede number.

### Problem B: English/Spanish continuation blocks missing
- **Root cause**: `_ADDRESS_BLOCK_WORDS` lacks EN patterns: `Building A`, `Block B`, `Floor 4`, `4th Floor`, `Apt 4B`, `Flat 2`, `Unit 2/7`, `Suite 300`.
- **Root cause**: Lacks ES patterns: `Edificio A`, `Portal A`, `Planta 3`, `Piso 2`, `Puerta 2/7`, `Bloque C`, `Escalera B`, `4º piso`.
- **Fix**: Add these patterns to `_ADDRESS_BLOCK_WORDS` and `_CONNECTOR_WORDS`.

### Problem C: Date fragments misclassified as POSTAL_ADDRESS
- **Root cause**: `NumberGroupingDetector` and `ContextNumberRecognizer` use `_infer_entity_type_from_context`; when both address hints (épület, utca) and date hints (szül., dob) appear, address can win.
- **Root cause**: Date-like patterns (`1989-08-17`, `17/08/1989`) match number-grouping; context has "szül." or "dob" but address hints (e.g. "cím") may also match.
- **Fix**: Add explicit **negative** context: when `szül|szül\.|dob|fecha de nacimiento|date of birth|born` appears, **never** return `POSTAL_ADDRESS` for date-shaped numbers (YYYY-MM-DD, DD/MM/YYYY).

### Problem D: Broken partial matches
- **Root cause**: `find_address_blocks` can produce `18-24., 2/7.` without real address prefix when numbers are close.
- **Fix**: Require at least one address block word **inside** the matched span, or in immediate context. Already present: `if not _ADDRESS_BLOCK_WORDS.search(matched): continue`. Strengthen: reject spans that are only `number, number` with no address word in between or before.

---

## 2. File-by-File Patch Plan

| File | Changes |
|------|---------|
| `span_extender.py` | Add EN continuation: `Building A`, `Block B`, `Floor 4`, `4th Floor`, `Apt 4B`, `Flat 2`, `Unit 2/7`, `Suite 300`. Add ES: `Edificio A`, `Portal A`, `Planta 3`, `Piso 2`, `Puerta 2/7`, `Bloque C`, `Escalera B`, `4º piso`. Add `flat`, `unit`, `block` to base lists. |
| `regex_detector.py` | Add shortened HU pattern: City, Name + Number. Add EN pattern with Apt/Flat/Unit/Suite. Add ES pattern with Edificio/Planta/Piso/Puerta. |
| `number_grouping_detector.py` | Add `_DATE_NEGATIVE_CONTEXT`; in `_infer_entity_type_from_context`, if date context and date-shaped number → return DATE/DATE_OF_BIRTH, never POSTAL_ADDRESS. |
| `context_number_recognizer.py` | Same negative context; add date-shaped pattern check; never return POSTAL_ADDRESS when DOB/date context. |
| `tests/` | New `test_address_detection.py` with pytest cases for HU/EN/ES full/shortened and date-not-address. |
