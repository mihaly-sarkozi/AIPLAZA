# PII & Knowledge Base – Coverage Matrix

Ez a mátrix azt mutatja, **mi van lefedve** és **mi hiányzik** a tesztsorban. Oszlopok: típusonkénti pozitív (HU/EN/ES), negatív, edge case, szanitizálás, file ingest, review flow.

**Jelölés:**
- **✓** = explicit, stabil teszt (unit vagy integration)
- **○** = részleges / xfail / „dokumentációs” teszt / egy másik tesztben érintve
- **✗** = nincs dedikált teszt
- **—** = nem alkalmazható

| Entity | Positive HU | Positive EN | Positive ES | Negative | Edge case | Sanitization | File ingest | Review flow |
|--------|:-----------:|:-----------:|:-----------:|:--------:|:---------:|:------------:|:-----------:|:-----------:|
| **email** | ✓ | ✓ | ○ | ✗ | ✓ | ✓ | ○ | ✓ |
| **phone** | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ○ | ○ |
| **IBAN** | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ○ | ○ |
| **bank account** | ✓ | ✓ | ✗ | ✓ | ○ | ✓ | ○ | ○ |
| **customer ID** | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ○ | ○ |
| **contract number** | ✓ | ○ | ✗ | ✗ | ✗ | ✓ | ○ | ○ |
| **ticket ID** | ✓ | ○ | ✗ | ✗ | ✗ | ✓ | ○ | ○ |
| **date / DOB** | ✓ | ○ | ✗ | ✗ | ✗ | ✓ | ○ | ○ |
| **name** | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ○ | ○ |
| **address** | ✓ | ○ | ✗ | ✗ | ✗ | ✓ | ○ | ○ |
| **vehicle registration** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ○ | ○ |
| **VIN** | ○ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ○ | ○ |
| **engine ID** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ○ | ○ |
| **IMEI** | ○ | ✓ | ✗ | ✓ | ○ | ✓ | ✓ | ○ | ○ |
| **MAC** | ○ | ✓ | ✗ | ✓ | ○ | ✓ | ✓ | ○ | ○ |
| **IP** | ○ | ✓ | ✗ | ✓ | ○ | ✓ | ✓ | ○ | ○ |
| **org email classification** | ✓ | ✓ | ✗ | ✗ | ✓ | — | — | ○ | ○ |
| **metadata** | — | — | — | — | — | — | — | ○ | — |

---

## Részletes leképezés (hol van teszt)

### Pozitív tesztek (HU / EN / ES)

| Entity | Fájl / osztály | Megjegyzés |
|--------|----------------|------------|
| email | `test_pii_gdpr_regex_detector` (EN), `test_pii_gdpr_email_classifier` (HU/EN), `test_pii_pipeline` TestKozvetlenSzemelyesAdatok | HU: Kovács + email, info@company.hu; EN: anna.kovacs@example.com |
| phone | `test_pii_gdpr_regex_detector` test_detects_phone_hu (HU), `test_pii_pipeline` test_telefonszam (+36, +34) | HU: +36 30…; ES: +34 612… |
| IBAN | `test_pii_gdpr_regex_detector` test_detects_iban (EN text), `test_pii_pipeline` TestPenzugyiAdatok | HU42 formátum |
| bank account | `test_dedicated_recognizers` TestBankAccountRecognizer (HU/EN), `test_pii_pipeline` csak IBAN | bankszámla: 24 digit, szóközök |
| customer ID | `test_pii_gdpr_regex_detector` test_detects_customer_id (HU), `test_pii_pipeline` TestErosSzemelyazonositok | UGY-*, CLIENT-*, #12345678 |
| contract number | `test_pii_pipeline` test_szerzodeszam | SZ-*, Szerződés-* (HU) |
| ticket ID | `test_pii_pipeline` test_ticket_id | JIRA-*, TKT-* (HU) |
| date / DOB | `test_pii_gdpr_regex_detector` test_detects_date_of_birth (HU), `test_pii_pipeline` test_szuletesi_datum | 1992.03.14, született:, dob: |
| name | `test_pii_pipeline` TestKozvetlenSzemelyesAdatok (HU/EN), pipeline Kovács Anna / John Smith; vehicle_detector ES Juan Pérez | HU/EN/ES név minták |
| address | `test_pii_pipeline` test_nev_es_email_egy_szovegben, test_lakcim_kiszurve_medium | 1123 Budapest, Alkotás utca 15. |
| vehicle registration | `test_pii_gdpr_regex_detector`, `test_pii_gdpr_vehicle_detector` (HU/ES), `test_pii_pipeline` TestJarmuAdatok, `test_context_scoring` | ABC-123, AB 12 CD 34, 1234 ABC (ES) |
| VIN | `test_pii_gdpr_vehicle_detector`, `test_pii_gdpr_pipeline` test_pipeline_vin_engine, `test_dedicated_recognizers` TestVINRecognizer | WVWZZZ1JZXW000001; EN |
| engine ID | `test_pii_gdpr_vehicle_detector`, `test_pii_gdpr_pipeline`, `test_dedicated_recognizers` TestEngineIDRecognizer (HU/EN), `test_context_scoring` | AB12CD345678, Motorszám (HU) |
| IMEI | `test_pii_gdpr_pipeline` test_pipeline_imei_mac, `test_dedicated_recognizers` TestIMEIRecognizer | 15 digit, labeled |
| MAC | `test_pii_gdpr_pipeline` test_pipeline_imei_mac, `test_dedicated_recognizers` TestMACRecognizer | 00:1A:2B:3C:4D:5E, colon/hyphen |
| IP | `test_dedicated_recognizers` TestIPRecognizer | IPv4, IPv6 (EN) |
| org email classification | `test_pii_gdpr_email_classifier` (personal/org/role), `test_pii_gdpr_pipeline` test_pipeline_info_company_email | role → KEEP, personal → MASK, policy outcomes |

### Negatív tesztek

| Entity | Fájl | Megjegyzés |
|--------|------|------------|
| phone | — | Nincs explicit „nem telefon” negatív |
| bank account | `test_dedicated_recognizers` test_negative_short_number | rövid szám → nem bankszámla |
| vehicle registration | `test_context_scoring` test_context_score_plate_negative_product | ABC-123 mint termékkód → alacsony score |
| VIN | `test_dedicated_recognizers` test_negative_16_chars, `test_context_scoring` test_context_score_vin_negative | 16 char, SKU kontextus |
| engine ID | `test_dedicated_recognizers` test_negative_unlabeled_digits, `test_context_scoring` test_context_score_engine_negative_sku | címke nélkül / SKU kontextus |
| IMEI | `test_dedicated_recognizers` test_negative_not_15_digits | 14 digit → nem IMEI |
| MAC | `test_dedicated_recognizers` test_negative_no_mac | Random text → 0 találat |
| IP | `test_dedicated_recognizers` test_negative_no_ip | No numbers or addresses → 0 |

### Edge case

| Entity | Fájl | Megjegyzés |
|--------|------|------------|
| email | `test_pii_gdpr_email_classifier` (personal vs org vs role), policy tests | MASK/REVIEW/KEEP döntések |
| vehicle registration | `test_context_scoring` test_pipeline_license_plate_vs_product_code | rendszám vs termékkód |
| VIN | `test_context_scoring` test_pipeline_vin_vs_random_17char, test_deduplicate_* (sanitization) | VIN vs random 17 char; longer wins |
| engine ID | `test_context_scoring` test_pipeline_engine_number_vs_sku | engine vs SKU |
| IMEI/MAC/IP | `test_dedicated_recognizers` edge tests (lowercase label, version-like 1.2.3.4) | címke változatok |
| org email classification | policy_personal_email_always_masked, policy_organizational_* | Konfig szerinti action |

### Sanitization

| Hol | Fájl | Megjegyzés |
|-----|------|------------|
| Standard placeholders | `test_pii_sanitization` test_standard_placeholders_*, test_unknown_type | [EMAIL_ADDRESS], [PERSON_NAME], [PHONE_NUMBER], stb. |
| Generalization | `test_pii_sanitization` test_generalization_* | contact person, specific date, postal address |
| Dedupe longer wins | `test_pii_sanitization` test_deduplicate_* | name in email, address in location |
| Offset-safe replace | `test_pii_sanitization` test_replacement_order_* | end-to-start, no corruption |
| pii_gdpr Sanitizer | `test_pii_gdpr_pipeline` test_sanitizer_mask | [EMAIL_ADDRESS] in sanitized_text |

### File ingest

| Hol | Fájl | Megjegyzés |
|-----|------|------------|
| Általános | `test_file_ingest` | plain TXT, empty TXT, DOCX metadata, empty PDF, scanned fallback; service empty/scanned status |
| Per-entity | — | Nincs entitás-specifikus file ingest teszt (pl. „PDF-ben email kiszűrve”) |

### Review flow

| Hol | Fájl | Megjegyzés |
|-----|------|------------|
| 409 + rich payload | `test_pii_review_flow` test_409_*, test_409_payload_has_entity_types_counts_snippets | detected_types, counts, snippets |
| Confirm continues | `test_pii_review_flow` test_confirmation_continues_processing | confirm_pii → add_training_log, [EMAIL_ADDRESS] |
| No confirm = not indexed | `test_pii_review_flow` test_without_confirmation_document_not_indexed | add_training_log not called |
| Reject | `test_pii_review_flow` test_reject_upload_does_not_store | status=rejected, not stored |
| Entitás | A review flow tesztek email PII-t használnak; más entitásra nincs dedikált review teszt | ○ |

---

## Hiányzó / gyenge lefedettség (összefoglalva)

1. **Pozitív ES**: email, IBAN, bank account, customer ID, contract, ticket, date, address, VIN, IMEI, MAC, IP – külön spanyol szöveges pozitív tesztek nagy része ✗ vagy ○.
2. **Negatív**: email, phone, IBAN, customer ID, contract, ticket, date, name, address – nincs explicit „nem PII” negatív teszt.
3. **Edge**: phone, IBAN, bank, customer ID, contract, ticket, date, name, address – kevés vagy nincs edge teszt.
4. **File ingest**: nincs entitás-szintű lefedettség (pl. „feltöltött PDF-ben email/telefon kiszűrve”).
5. **Review flow**: csak email-alapú; többi entitásra nincs külön review teszt.
6. **Metadata**: file ingest DOCX author/modified_by tesztelt; általános „metadata” oszlop N/A vagy ○.

---

## Futtatás

- **Unit (PII)**: `pytest tests/unit/test_pii_*.py tests/unit/test_dedicated_recognizers.py tests/unit/test_context_scoring.py -v`
- **Integration (PII + policy + replace)**: `pytest tests/integration/test_pii_pipeline.py tests/integration/test_pii_review_flow.py -v`
- **File ingest**: `pytest tests/integration/test_file_ingest.py -v`
- **Sanitization**: `pytest tests/unit/test_pii_sanitization.py -v`

A „not yet implemented” / xfail tesztek: `tests/integration/test_pii_pipeline.py` `TestNemImplementaltTipusok`, és `docs/NOT_YET_SUPPORTED.md`.
