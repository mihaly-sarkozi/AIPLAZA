# Minimum Release Acceptance Suite

A **ship előtti minőségi kapu**: az alábbi tesztsor minden tesztjének át kell mennie, mielőtt a rendszert „használhatónak” nyilvánítanánk.

Futtatás:

```bash
pytest -m release_acceptance -v
```

Kb. **42** teszt tartozik a suitehez. A `test_plain_text_pdf_extraction` skipelődik, ha nincs reportlab; a többi nem függ tőle. Lassú tesztek nincsenek a suite-ben (a slow markerűeket kihagytuk).

---

## 1. Must-pass unit tests (entitásfelismerés)

Minden sorban legalább egy unit tesztnek át kell mennie.

| Entity | Test(s) |
|--------|---------|
| **email** | `test_pii_gdpr_regex_detector::test_detects_email`, `test_pii_gdpr_email_classifier::test_classify_personal_free` |
| **phone** | `test_pii_gdpr_regex_detector::test_detects_phone_hu` |
| **IBAN** | `test_pii_gdpr_regex_detector::test_detects_iban` |
| **name** | `test_pii_pipeline::TestKozvetlenSzemelyesAdatok::test_teljes_nev_kiszurve_medium` (integration) |
| **address** | `test_pii_pipeline::TestNemImplementaltTipusok::test_lakcim_kiszurve_medium` (integration) |
| **Hungarian plate** | `test_pii_gdpr_regex_detector::test_detects_vehicle_registration`, `test_pii_gdpr_vehicle_detector::test_hu_plate` |
| **Spanish plate** | `test_pii_gdpr_vehicle_detector::test_spanish_plate` |
| **VIN** | `test_pii_gdpr_vehicle_detector::test_vin_labeled`, `test_dedicated_recognizers::TestVINRecognizer::test_positive_labeled` |
| **IMEI** | `test_dedicated_recognizers::TestIMEIRecognizer::test_positive_labeled` |
| **MAC** | `test_dedicated_recognizers::TestMACRecognizer::test_positive_colon` |
| **IP** | `test_dedicated_recognizers::TestIPRecognizer::test_positive_ipv4` |
| **customer ID** | `test_pii_gdpr_regex_detector::test_detects_customer_id` |
| **contract number** | `test_pii_pipeline::TestErosSzemelyazonositok::test_szerzodeszam` (integration) |
| **ticket ID** | `test_pii_pipeline::TestErosSzemelyazonositok::test_ticket_id` (integration) |

---

## 2. Must-pass integration tests

| Requirement | Test(s) |
|-------------|---------|
| **Plain text input** | `test_pii_pipeline::TestKozvetlenSzemelyesAdatok::test_nev_es_email_egy_szovegben`, `test_pii_pipeline::TestPolicyEsReplace::test_apply_pii_replacements_helyettesit` |
| **PDF input** | `test_file_ingest::test_plain_text_pdf_extraction` (skip ha nincs reportlab), `test_file_ingest::test_empty_pdf_marked_as_empty_or_scanned` |
| **PII review 409** | `test_pii_review_flow::test_409_returned_when_pii_found`, `test_pii_review_flow::test_409_payload_has_entity_types_counts_snippets` |
| **Post-confirmation indexing** | `test_pii_review_flow::test_confirmation_continues_processing` |
| **Sanitized replacement stored correctly** | `test_pii_review_flow::test_confirmation_continues_processing` (content has `[EMAIL_ADDRESS]`), `test_pii_pipeline::TestPolicyEsReplace::test_apply_pii_replacements_helyettesit` |
| **Raw PII handled separately** | `test_pii_review_flow::test_confirmation_continues_processing` (raw_content and review_decision stored) |

---

## 3. Must-pass policy tests

| Requirement | Test(s) |
|-------------|---------|
| **Personal email masked** | `test_pii_gdpr_email_classifier::test_policy_personal_email_always_masked` |
| **Role-based email configurable** | `test_pii_gdpr_email_classifier::test_policy_role_based_keep_by_default`, `test_policy_role_based_review_when_configured`, `test_policy_role_based_masked_when_not_allowed` |
| **Date allow/block behavior works** | `test_pii_pipeline::TestPolicyEsReplace::test_weak_csak_email_telefon` (weak: no date), `test_medium_tartalmazza_nevet` (medium: date allowed), `test_pii_pipeline::TestKozvetlenSzemelyesAdatok::test_szuletesi_datum_kiszurve_medium` |
| **Organization/location sensitivity config works** | `test_pii_pipeline::TestPolicyEsReplace::test_strong_tartalmazza_szervezet_helyet` |

---

## Összefoglaló

- **Unit (entity)**: regex_detector (email, phone, IBAN, customer ID, HU plate, DOB), vehicle_detector (HU plate, ES plate, VIN), dedicated_recognizers (VIN, IMEI, MAC, IP), email_classifier (email + policy). Name, address, contract, ticket: integration test_pii_pipeline.
- **Integration**: plain text + replace (test_pii_pipeline), PDF + empty (test_file_ingest), PII review 409 + post-confirm + sanitized + raw (test_pii_review_flow).
- **Policy**: personal email MASK, role-based KEEP/REVIEW/MASK config, sensitivity weak/medium/strong (date in medium, org/place in strong).

Ha a `pytest -m release_acceptance -v` sikeres, a minimum release acceptance suite zöld.
