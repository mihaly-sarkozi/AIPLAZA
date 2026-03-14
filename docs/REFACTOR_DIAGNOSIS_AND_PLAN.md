# Knowledge + PII/GDPR Refactor: Diagnosis and Plan

## 1. Short diagnosis of the current codebase

- **Package root:** The project uses **`apps`** (and **`config`**) as top-level packages; code lives under `apps/knowledge/`. Imports are consistently `from apps.knowledge....` Tests and main.py use the same. `pytest.ini` and `pyproject.toml` set `pythonpath = .` so that `apps` is found when the project root is on the path. **No duplicated root** (e.g. no separate `knowledge/` at repo root). See **docs/PACKAGING.md** for the single package/import strategy.
- **PII layers:** Detection is implemented in **`pii_gdpr`** (IngestionPipeline, detectors, policy engine, sanitizer). The **`pii`** package is a compatibility layer: `filter_pii` / `apply_pii_replacements` try the pii_gdpr adapter first, then fall back to legacy pipeline. Duplication exists in **entity lists**: `pii/entities.py` defines `SUPPORTED_LEGACY_NAMES` (10 items), while `pii/policy.py` defines `WEAK_ENTITIES`, `MEDIUM_ENTITIES`, `STRONG_ENTITIES` (many more) independently. The adapter and sanitizer use legacy type names but do not import from a single “supported list” module.
- **Tests:** `test_pii_pipeline.py` has strong assertions for most cases; weak spots: (1) `test_vin_imei_mac_detektalva_legacy_adapteren_keresztul` only checks “at least one of VIN/IMEI/MAC” and “len(matches) >= 2” without asserting each entity type and a concrete value; (2) xfail tests in `TestNemImplementaltTipusok` only do `assert isinstance(matches, list)` and do not assert the absence of the not-yet-supported type; (3) `test_lakcim_kiszurve_medium` is a real, passing test but sits inside a class marked `@pytest.mark.expected_fail_not_implemented`, which is misleading. `test_pii_review_flow.py` and `test_file_ingest.py` are already strong; a few file_ingest tests could be marked `release_acceptance` for consistency.
- **Missing structure:** Subpackages `application`, `presentation`, `infrastructure`, `domain`, `ports`, `adapter` under `apps/knowledge/` have no `__init__.py`; they work as namespace packages but adding `__init__.py` makes the package layout explicit and avoids subtle import issues.
- **pytest markers:** `pytest.ini` defines `release_acceptance`; `pyproject.toml` does not. Keeping both in sync avoids CI/IDE confusion.

---

## 2. Prioritized list of issues

| Priority   | Issue | Action |
|-----------|--------|--------|
| **Blocker** | No single source of truth for supported entities; `entities.py` and `policy.py` define overlapping sets independently. | Unify in `pii/entities.py`: implemented / partial / not-yet; policy imports WEAK/MEDIUM/STRONG from entities. |
| **High**    | test_lakcim is a real must-pass test but lives under a class marked expected_fail_not_implemented. | Move `test_lakcim_kiszurve_medium` out of `TestNemImplementaltTipusok` into a normal test class. |
| **High**    | test_vin_imei_mac does not assert each of VIN, IMEI, MAC with concrete detected value. | Strengthen: require at least one match per type and assert expected substring in matched text. |
| **Medium**  | xfail tests only assert `isinstance(matches, list)`; they don’t assert “this type is not detected”. | Add explicit assert that the not-yet-supported type is not in match types (or document that we only assert no crash). |
| **Medium**  | Missing `__init__.py` in knowledge/application, presentation, infrastructure, domain, ports, adapter. | Add empty (or minimal) `__init__.py` so these are explicit packages. |
| **Low**     | pyproject.toml markers don’t include `release_acceptance`. | Add `release_acceptance` to `[tool.pytest.ini_options]` markers. |
| **Low**     | File ingest tests: docx and train_from_file status tests not marked release_acceptance. | Add `@pytest.mark.release_acceptance` where they act as quality gates. |

---

## 3. Patch plan (concrete code changes)

1. **Unify entities**  
   - In `apps/knowledge/pii/entities.py`: Define `IMPLEMENTED_LEGACY_NAMES`, `PARTIAL_LEGACY_NAMES`, `NOT_YET_LEGACY_NAMES`, and `WEAK_ENTITIES`, `MEDIUM_ENTITIES`, `STRONG_ENTITIES` (sensitivity sets). Implemented = baseline supported; partial = detector exists but not full; not-yet = backlog.  
   - In `apps/knowledge/pii/policy.py`: Remove local `WEAK_ENTITIES` / `MEDIUM_ENTITIES` / `STRONG_ENTITIES`; import them from `entities` and re-export `entities_for_sensitivity` unchanged (so callers keep using `policy.entities_for_sensitivity`).

2. **Tests**  
   - **test_pii_pipeline.py:** Move `test_lakcim_kiszurve_medium` from `TestNemImplementaltTipusok` into `TestKozvetlenSzemelyesAdatok` (or a dedicated “Address” class).  
   - **test_pii_pipeline.py:** Strengthen `test_vin_imei_mac_detektalva_legacy_adapteren_keresztul`: assert that there is at least one match for `vin` containing `WVWZZZ1JZXW000001`, at least one for `imei` containing `490154203237518`, and at least one for `mac_cím` containing `00:1A:2B:3C:4D:5E` (or equivalent).  
   - **test_pii_pipeline.py:** In xfail tests (e.g. test_taj_ado, test_bankkartya_szam_nincs, test_ip_cim_nincs, test_gps), add an explicit assert that the relevant entity type is not in `{m[2] for m in matches}` (so we document “we do not yet detect this”).  
   - **test_file_ingest.py:** Add `@pytest.mark.release_acceptance` to `test_docx_with_metadata`, `test_train_from_file_returns_empty_status_when_extract_empty`, `test_train_from_file_returns_scanned_review_required_when_extract_sparse`.

3. **Packaging**  
   - Add empty `__init__.py` under `apps/knowledge/application`, `presentation`, `infrastructure`, `domain`, `ports`, and `adapter` (and `adapter/http` if missing).

4. **pytest**  
   - In `pyproject.toml` under `[tool.pytest.ini_options]`, add the `release_acceptance` marker to the `markers` list so it matches `pytest.ini`.

5. **Preserve behavior**  
   - No change to file ingest return values (ok / empty / scanned_review_required), PII 409 flow, confirm/reject storage, or placeholder names (`[EMAIL_ADDRESS]`, etc.). Adapter and sanitizer keep using legacy type names; they remain consistent with the unified entities module.

---

## 4. How to run

### Install

```bash
cd /path/to/AIPLAZA
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
pip install -r requirements.txt
```

Installing with `-e .` puts the project on the path so `apps.knowledge` resolves. Alternatively, ensure the project root is on `PYTHONPATH` (e.g. `export PYTHONPATH=.`).

### Pytest commands

```bash
# All tests
pytest

# Unit only
pytest -m unit

# Integration only
pytest -m integration

# Release acceptance suite (minimum gate before ship)
pytest -m release_acceptance -v

# Exclude slow
pytest -m "not slow"

# Focus on PII + file ingest
pytest tests/unit/test_pii_sanitization.py tests/unit/test_pii_gdpr_regex_detector.py tests/integration/test_pii_pipeline.py tests/integration/test_pii_review_flow.py tests/integration/test_file_ingest.py -v
```

### Recommended CI commands

```bash
# Fast gate: release acceptance, no slow
pytest -m "release_acceptance and not slow" -v

# Full suite (including slow) for nightly or pre-release
pytest -v
```

---

## 5. Summary

- **Package root:** Stays `apps` + `config` with `pythonpath = .`; no change to import style. Single strategy documented in **docs/PACKAGING.md**.  
- **PII source of truth:** `pii_gdpr` remains the implementation; `pii` stays the adapter. **Single list of entities** lives in `pii/entities.py`; policy imports sensitivity sets from it.  
- **Tests:** One real test moved out of xfail class; VIN/IMEI/MAC test strengthened; xfail tests given a clear “no such type” assert; release_acceptance added on selected file_ingest tests.  
- **Packaging:** Explicit `__init__.py` under knowledge subpackages; pytest markers aligned between pytest.ini and pyproject.toml.
