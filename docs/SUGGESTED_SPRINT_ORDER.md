# Suggested Sprint Order

Javasolt sprint felosztás a PII / tudástár / file ingest és review flow stabilizálásához. A sorrend célja: először az alapok, majd detektorok, nyelv és policy, végül ingest + review és keményítés.

---

## Sprint 1 — Stabilize the base

**Cél:** Konzisztens csomagstruktúra, futó tesztek, egyértelmű címkézés, támogatott vs nem-támogatott entitáslista.

| Téma | Tartalom | Megjegyzés |
|------|----------|------------|
| **Package structure** | `pii` vs `pii_gdpr` szerepkör, adapter réteg, egyértelmű belépési pontok | Lásd: `PII_MIGRATION_DECISION.md` |
| **Runnable tests** | Unit + integration tesztek futtathatók `pytest`-tel, függőségek (spacy/stanza/reportlab) dokumentálva vagy opcionális | `pytest tests/unit tests/integration` |
| **Test labeling** | `unit`, `integration`, `slow`, `must_pass`, `release_acceptance`, `xfail` / `expected_fail_not_implemented` | `pytest.ini` markers |
| **Supported / not-supported entity lists** | Hivatalos lista: mely entitásokra garantált a viselkedés; „nem még támogatott” lista | `NOT_YET_SUPPORTED.md`, policy `entities_for_sensitivity` |

**Kimenet:** Tiszta alap: ki mit futtat, mit várhat el, mely típusok „supported”.

---

## Sprint 2 — Missing detectors

**Cél:** Hiányzó vagy gyenge detektorok pótlása / erősítése (IP, MAC, IMEI, VIN, motor/alváz, bankszámla).

| Téma | Tartalom | Megjegyzés |
|------|----------|------------|
| **IP** | IPv4 / IPv6 detektálás, policy-be illesztés, negatív (pl. verziószám) edge | Unit: `test_dedicated_recognizers` TestIPRecognizer; adapter/pii_gdpr path |
| **MAC** | MAC cím formátumok (colon, hyphen), policy | Unit: TestMACRecognizer |
| **IMEI** | 15 digit + címke, policy | Unit: TestIMEIRecognizer |
| **VIN** | 17 karakter, kontextus (VIN vs random), policy | Unit: VehicleDetector, VINRecognizer; context scoring |
| **Engine / chassis** | Motorszám, alvázszám, kontextus (engine vs SKU) | Unit: EngineIDRecognizer, VehicleDetector; context scoring |
| **Bank account** | Bankszámla formátumok (HU 24 digit, dashed), policy | Unit: BankAccountRecognizer; legacy medium |

**Kimenet:** Ezek az entitások detektálódnak és a policy/placeholder listába illeszkednek; tesztek must_pass / release_acceptance.

---

## Sprint 3 — Multilingual and email policy

**Cél:** Spanyol minták, vegyes nyelv kezelés, email osztályozó és role-based email policy.

| Téma | Tartalom | Megjegyzés |
|------|----------|------------|
| **Spanish patterns** | Rendszám (matrícula), dátum, cím, név minták ES-re; nyelvdetektálás → ES path | Pipeline + regex/NER ES |
| **Mixed-language handling** | Dokumentum több nyelvű: nyelv per szegmens vagy egész doc; ütközés kezelés | Pipeline / analyzer |
| **Email classifier** | Personal vs organizational vs role-based; confidence | `EmailClassifier`, `test_pii_gdpr_email_classifier` |
| **Role-based email policy** | Konfig: KEEP / REVIEW / MASK role-based emailre; allow_organizational, allow_role_based | `PolicyConfig`, `PolicyEngine`; policy tesztek |

**Kimenet:** ES és vegyes nyelv megbízhatóan működik; email policy konfigurálható és tesztekkel lefedve.

---

## Sprint 4 — File ingest and review

**Cél:** Rétegezett file pipeline, metaadat, scan/OCR jelzés, end-to-end review flow.

| Téma | Tartalom | Megjegyzés |
|------|----------|------------|
| **Layered file pipeline** | Raw file → extracted text + metadata → sanitized → stored chunks | `file_ingest.py`, `train_from_file` refaktor |
| **Metadata** | Filename, author, creator, modified_by (PDF/DOCX); válaszban és opcionálisan tárolva | `FileMetadata`, `_metadata_for_response` |
| **Scan / OCR fallback signaling** | Üres vagy ritka szöveg → status empty / scanned_review_required, nem brutál ValueError | `MIN_EXTRACTED_TEXT_LEN`, `STATUS_*` |
| **End-to-end review flow** | 409 + rich payload (types, counts, snippets); confirm → indexing; reject; raw_content + review_decision tárolás | `test_pii_review_flow`, `PiiReviewDecision`, `add_block` |

**Kimenet:** Feltöltés biztonságos, átlátható; review flow backend-ben kész, tesztekkel.

---

## Sprint 5 — Hardening

**Cél:** Kontextus scoring, offset-biztos szanitizer, deduplikáció, coverage mátrix kész, CI minőségi kapu.

| Téma | Tartalom | Megjegyzés |
|------|----------|------------|
| **Context scoring** | Pozitív/negatív kulcsszavak, proximity, composite score; küszöbök (mask/review/ignore) | `context_scorer`, `test_context_scoring`; engine vs SKU, VIN vs random, plate vs product |
| **Offset-safe sanitizer** | Helyettesítés végtől elejig; szomszédos spanok nem romlanak | `apply_pii_replacements` (sanitization), unit tesztek |
| **Deduplication** | Átfedő detektálások: hosszabb nyer (név az emailben, cím a helyben) | `deduplicate_matches_longer_wins`, adapter + pipeline |
| **Coverage matrix completion** | Mátrix: entitás × (Positive HU/EN/ES, Negative, Edge, Sanitization, File ingest, Review flow) | `COVERAGE_MATRIX.md` |
| **CI quality gate** | Minimum release acceptance suite; minden ship előtt zöld | `pytest -m release_acceptance`, `MINIMUM_RELEASE_ACCEPTANCE.md` |

**Kimenet:** Szanitizálás és helyettesítés stabil; lefedettség explicit; CI blokkol, ha a release suite nem zöld.

---

## Összefoglaló

| Sprint | Fókusz |
|--------|--------|
| **1** | Alap: csomagstruktúra, tesztek, címkézés, supported/not-supported lista |
| **2** | Detektorok: IP, MAC, IMEI, VIN, engine/chassis, bankszámla |
| **3** | Többnyelv + email policy: spanyol, vegyes nyelv, email classifier, role-based policy |
| **4** | File ingest + review: rétegek, metaadat, scan/OCR jelzés, review flow E2E |
| **5** | Keményítés: context scoring, offset-safe sanitizer, dedupe, coverage mátrix, CI gate |

A 4. és 5. sprint nagy része már megvalósult (file ingest, review flow, sanitization/dedupe, coverage matrix, release acceptance suite); a dokumentum továbbra is hasznos mint **sprint order referencia** és **backlog** a hiányzó elemekhez (pl. több ES minta, CI-be kötés).
