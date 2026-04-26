from __future__ import annotations

import pytest

from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.knowledge_trace_service import _trace_claim_extraction_fields
from apps.knowledge.service.claim_typing import debug_claim_type
from apps.knowledge.service.language_rules import detect_language, fold_text, resolve_language
from apps.knowledge.service.mention_extractor import MentionExtractor
from apps.knowledge.service.space_time_extractor_v1 import SpaceTimeExtractorV1
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _extract_claims(text: str, language: str | None = None):
    resolved_language = detect_language(text, preferred_language=language)
    sentence = Sentence(text_content=text, metadata={"language": resolved_language})
    mentions = MentionExtractor().extract(sentence, language=resolved_language)
    claims = ClaimExtractorV1().extract(sentence, mentions, language=resolved_language)

    print(f"[TEST SENTENCE] language={resolved_language} text={text}")
    ClaimExtractorV1.debug_print(sentence, claims, language=resolved_language)
    for claim in claims:
        debug_claim_type(claim)

    return sentence, mentions, claims, resolved_language


def test_claim_extractor_hu(capsys: pytest.CaptureFixture[str]) -> None:
    _sentence, _mentions, claims, language = _extract_claims(
        "A login rendszer kétfaktoros azonosítást használ."
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert language == "hu"
    assert "login" in claim.subject_text.lower()
    assert "használ" in claim.predicate.lower()
    assert claim.claim_type in {"stable_descriptor", "relation"}
    assert claim.claim_status == "active"
    output = capsys.readouterr().out
    assert "[CLAIM DEBUG]" in output
    assert "language=hu" in output


def test_claim_extractor_hu_descriptor_keeps_enumerated_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "A Knowledge modul mondatokat, mentionöket és claim-eket készít.",
        language="hu",
    )

    claim = claims[0]
    assert claim.subject_text == "Knowledge modul"
    assert claim.predicate.lower() == "készít"
    assert "mentionöket" in (claim.object_text or "").lower()
    assert "claim-eket" in (claim.object_text or "").lower()


def test_claim_extractor_hu_felelose_title_relation() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Nagy Eszter a Zalka 2000 adatvédelmi felelőse.",
        language="hu",
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.subject_text == "Nagy Eszter"
    assert claim.predicate_text == "adatvédelmi felelőse"
    assert claim.object_text == "Zalka 2000"
    assert claim.claim_group == "relation"


def test_claim_extractor_hu_context_carryover_candidate_survives_quality_gate() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Korábban a belső incidenskezelési folyamatért felelt.",
        language="hu",
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.subject_text == ""
    assert claim.predicate_text == "felelt"
    assert claim.object_text == "belső incidenskezelési folyamatért"
    assert claim.metadata.get("quality_gate_context_carryover_candidate") is True


@pytest.mark.parametrize("trigger", ["Előtte", "Később", "Akkoriban"])
def test_claim_extractor_hu_context_trigger_candidate_survives_quality_gate(trigger: str) -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        f"{trigger} a belső incidenskezelési folyamatért felelt.",
        language="hu",
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.subject_text == ""
    assert claim.predicate_text == "felelt"
    assert claim.object_text == "belső incidenskezelési folyamatért"
    assert claim.metadata.get("quality_gate_context_carryover_candidate") is True


def test_claim_extractor_hu_source_phrase_sanitizes_admin_user_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "A dokumentum szerint az admin felhasználónak kötelező kétfaktoros azonosítást használnia.",
        language="hu",
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.subject_text == "admin felhasználó"
    assert claim.predicate_text == "kötelező"
    assert claim.object_text == "kétfaktoros azonosítást használnia"
    assert claim.metadata.get("sanitizers_applied") == ["source_phrase", "suffix_normalization"]
    fields = _trace_claim_extraction_fields(claim)
    assert fields.get("subject_source") == "sanitized"
    assert fields.get("sanitizers_applied") == ["source_phrase", "suffix_normalization"]


def test_claim_extractor_en_temporal_opener_does_not_leak_into_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Later, the account was updated in April 2026.",
        language="en",
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.subject_text == "account"
    assert claim.predicate.lower() == "was updated"
    assert "april 2026" in (claim.object_text or "").lower()
    assert claim.metadata.get("sanitizers_applied") == ["temporal_opener_strip"]


def test_claim_extractor_en_source_phrase_does_not_leak_into_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "According to the document, the legacy import module was deprecated in 2024.",
        language="en",
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.subject_text == "legacy import module"
    assert "according to the document" not in fold_text(claim.subject_text)


def test_claim_extractor_and_subject_context_hu_nagy_eszter_carryover() -> None:
    texts = [
        "Nagy Eszter a Zalka 2000 adatvédelmi felelőse.",
        "Korábban a belső incidenskezelési folyamatért felelt.",
    ]
    rows = []
    for index, text in enumerate(texts):
        sentence, mentions, claims, language = _extract_claims(text, language="hu")
        rows.append(
            {
                "sentence_id": str(sentence.id),
                "order_index": index,
                "text": text,
                "language": language,
                "mentions": mentions,
                "claims": claims,
            }
        )

    resolved = SubjectContextResolverV1().resolve_claims(rows)

    first = resolved[0]["claims"][0]
    second = resolved[1]["claims"][0]
    assert first.subject_text == "Nagy Eszter"
    assert first.predicate_text == "adatvédelmi felelőse"
    assert first.object_text == "Zalka 2000"
    assert second.subject_text == "Nagy Eszter"
    assert second.predicate_text == "felelt"
    assert second.object_text == "belső incidenskezelési folyamatért"
    assert second.metadata.get("context_subject_applied") is True
    assert second.metadata.get("context_subject_reason") == "implicit_subject"


def test_claim_extractor_en_search_module_uses_qdrant_index() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "The search module uses Qdrant index.",
        language="en",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert claim.subject_text == "search module"
    assert claim.predicate.lower() == "uses"
    assert "qdrant index" in (claim.object_text or "").lower()


def test_claim_extractor_en_account_created_january_updated_may() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "The account was created in January 2025 and updated in May 2026.",
        language="en",
    )

    assert len(claims) >= 2
    assert claims[0].subject_text == "account"
    assert claims[0].predicate.lower() == "was created"
    assert "january 2025" in (claims[0].object_text or "").lower()
    assert claims[1].subject_text == "account"
    assert claims[1].predicate.lower() == "updated"
    assert "may 2026" in (claims[1].object_text or "").lower()


def test_claim_extractor_en_compliance_lead_at() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Jane Doe is the compliance lead at Acme Corp.",
        language="en",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert claim.subject_text == "Jane Doe"
    assert "lead" in claim.predicate.lower()
    assert "acme" in (claim.object_text or "").lower()


def test_claim_extractor_en(capsys: pytest.CaptureFixture[str]) -> None:
    _sentence, _mentions, claims, language = _extract_claims(
        "The login system uses two-factor authentication."
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert language == "en"
    assert claim.subject_text == "login system"
    assert claim.predicate.lower() == "uses"
    assert "two-factor authentication" in (claim.object_text or "").lower()
    assert claim.claim_type in {"stable_descriptor", "relation"}
    output = capsys.readouterr().out
    assert "[CLAIM DEBUG]" in output
    assert "language=en" in output


def test_claim_extractor_es(capsys: pytest.CaptureFixture[str]) -> None:
    _sentence, _mentions, claims, language = _extract_claims(
        "El sistema de inicio de sesión utiliza autenticación de dos factores."
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert language == "es"
    assert claim.subject_text == "sistema de inicio de sesión"
    assert claim.predicate.lower() == "utiliza"
    assert "autenticación de dos factores" in (claim.object_text or "").lower()
    assert claim.claim_type in {"stable_descriptor", "relation"}
    output = capsys.readouterr().out
    assert "[CLAIM DEBUG]" in output
    assert "language=es" in output


def test_claim_extractor_es_search_module_openai_embeddings() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "El módulo de búsqueda utiliza embeddings de OpenAI.",
        language="es",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert "módulo de búsqueda" in (claim.subject_text or "").lower() or "modulo de busqueda" in fold_text(
        claim.subject_text or ""
    )
    assert claim.predicate.lower() == "utiliza"
    assert "openai" in (claim.object_text or "").lower()
    assert "embedding" in (claim.object_text or "").lower()


def test_claim_extractor_es_account_enero_mayo() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "La cuenta fue creada en enero de 2025 y actualizada en mayo de 2026.",
        language="es",
    )

    assert len(claims) >= 2
    assert claims[0].subject_text == "cuenta"
    assert claims[0].predicate.lower() == "fue creada"
    assert "enero de 2025" in (claims[0].object_text or "").lower()
    assert claims[1].subject_text == "cuenta"
    assert claims[1].predicate.lower() == "actualizada"
    assert "mayo de 2026" in (claims[1].object_text or "").lower()


def test_claim_extractor_es_carlos_compliance_responsable() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Carlos García es el responsable de compliance en Zalka 2000.",
        language="es",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert "carlos" in (claim.subject_text or "").lower() and "garcía" in (claim.subject_text or "").lower()
    assert claim.predicate.lower() == "es"
    o = (claim.object_text or "").lower()
    assert "responsable" in o and "compliance" in o and "zalka" in o


def test_claim_extractor_es_estaba_inactiva_en_2024() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "La sucursal estaba inactiva en 2024.",
        language="es",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert "sucursal" in (claim.subject_text or "").lower()
    assert "inactiva" in claim.predicate.lower()
    assert "2024" in (claim.object_text or "")


def test_claim_extractor_es_fue_responsable_anteriormente() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Carlos García fue responsable anteriormente de la auditoría interna.",
        language="es",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert "carlos" in (claim.subject_text or "").lower()
    assert claim.predicate.lower() == "responsable"
    assert "auditoría" in (claim.object_text or "").lower() or "auditoria" in fold_text(claim.object_text or "")


def test_claim_extractor_es_fue_desactivado() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "El módulo de facturación fue desactivado en abril de 2026.",
        language="es",
    )

    assert len(claims) >= 1
    claim = claims[0]
    assert "desactivado" in claim.predicate.lower() or "fue desactivado" in claim.predicate.lower()
    assert "abril" in (claim.object_text or "").lower()


def test_claim_extractor_hu_state_subject_is_not_article() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("A Budapesti iroda jelenleg aktív.", language="hu")

    claim = claims[0]
    assert claim.subject_text == "Budapesti iroda"
    assert claim.claim_type == "state"
    assert claim.predicate.lower() in {"aktív", "aktiv"}


def test_claim_extractor_state_drops_pronoun_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "The London office is currently active it.",
        language="en",
    )

    claim = claims[0]
    assert claim.subject_text == "London office"
    assert claim.predicate.lower() == "is currently active"
    assert claim.object_text is None


def test_claim_extractor_state_drops_clause_start_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "La oficina de Madrid está actualmente activa en 2024 estaba.",
        language="es",
    )

    claim = claims[0]
    assert claim.subject_text == "oficina de Madrid"
    assert claim.predicate.lower() == "está actualmente activa"
    assert claim.object_text is None


def test_claim_extractor_but_clause_keeps_first_state_clean_and_extracts_followup() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "The London office is currently active, but it was inactive before February 2025.",
        language="en",
    )

    assert len(claims) >= 2
    assert claims[0].subject_text == "London office"
    assert claims[0].predicate.lower() == "is currently active"
    assert claims[0].object_text is None
    assert any(claim.predicate.lower() == "was inactive" for claim in claims[1:])
    assert any("before february 2025" in (claim.object_text or "").lower() for claim in claims[1:])


def test_claim_extractor_spanish_but_clause_keeps_first_state_clean() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "La oficina de Madrid está actualmente activa, pero estaba inactiva antes de febrero de 2025.",
        language="es",
    )

    assert len(claims) >= 2
    assert claims[0].subject_text == "oficina de Madrid"
    assert claims[0].predicate.lower() == "está actualmente activa"
    assert claims[0].object_text is None
    assert any("inactiva" in claim.predicate.lower() for claim in claims[1:])
    assert any("antes de febrero de 2025" in (claim.object_text or "").lower() for claim in claims[1:])


def test_claim_extractor_hu_prefers_short_subject_mention_and_prepredicate_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("A login rendszer kétfaktoros azonosítást igényel.", language="hu")

    claim = claims[0]
    assert claim.subject_text == "login rendszer"
    assert claim.predicate.lower() == "igényel"
    assert "kétfaktoros azonosítást" in (claim.object_text or "").lower()


def test_claim_extractor_hu_module_sentence_keeps_object_out_of_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("A modul Qdrant indexet használ a kereséshez.", language="hu")

    claim = claims[0]
    assert claim.subject_text == "modul"
    assert claim.predicate.lower() == "használ"
    assert "qdrant indexet" in (claim.object_text or "").lower()
    md = claim.metadata or {}
    assert md.get("pattern_name") == "hu_use_object_before_predicate"
    assert md.get("extraction_pattern") == md.get("pattern_name")
    assert md.get("extraction_language") == "hu"


def test_claim_extractor_hu_long_subject_rewrites_to_best_prepredicate_mention() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "A keresési modul OpenAI embeddinget és Qdrant vektorindexet használ.",
        language="hu",
    )

    claim = claims[0]
    assert claim.subject_text == "keresési modul"
    assert claim.predicate.lower() == "használ"
    assert "openai embeddinget" in (claim.object_text or "").lower()
    assert "qdrant vektorindexet" in (claim.object_text or "").lower()


def test_claim_extractor_hu_relation_subject_prefers_person_entity() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("Kovács Péter a Zalka 2000 ügyféltámogatási vezetője.", language="hu")

    claim = claims[0]
    assert claim.subject_text == "Kovács Péter"
    assert claim.predicate.lower() == "vezetője"
    assert claim.object_text == "Zalka 2000 ügyféltámogatási"


def test_claim_extractor_hu_long_relation_subject_prefers_person_mention() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Nagy Anna a Zalka 2000 compliance vezetője.",
        language="hu",
    )

    claim = claims[0]
    assert claim.subject_text == "Nagy Anna"
    assert claim.predicate.lower() == "vezetője"
    assert claim.object_text == "Zalka 2000 compliance"


def test_claim_extractor_hu_relation_keeps_title_object_before_followup_clause() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Nagy Anna a Zalka 2000 compliance vezetője, korábban a belső audit folyamatért felelt.",
        language="hu",
    )

    title_claim = next(claim for claim in claims if claim.predicate.lower() == "vezetője")
    historical_claim = next(claim for claim in claims if claim.predicate.lower() == "felelt")
    assert title_claim.subject_text == "Nagy Anna"
    assert title_claim.object_text == "Zalka 2000 compliance"
    assert historical_claim.subject_text == "Nagy Anna"
    assert historical_claim.object_text == "belső audit folyamatért"


def test_claim_extractor_hu_modal_use_sentence_drops_weak_contextual_duplicate() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "A login rendszer admin felhasználóknál kötelező kétfaktoros azonosítást használ.",
        language="hu",
    )

    assert any(claim.predicate.lower() == "kötelező" and "kétfaktoros azonosítást" in (claim.object_text or "").lower() for claim in claims)
    assert not any(claim.predicate.lower() == "használ" and "admin felhasználóknál" in (claim.object_text or "").lower() for claim in claims)


def test_claim_extractor_en_rule_uses_real_subject_and_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("The user must accept the privacy policy.", language="en")

    claim = claims[0]
    assert claim.subject_text == "user"
    assert claim.predicate.lower() == "must"
    assert claim.object_text == "accept the privacy policy"
    assert claim.claim_type == "rule_procedure"


def test_claim_extractor_es_event_avoids_year_as_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("La cuenta fue creada en marzo de 2025.", language="es")

    claim = claims[0]
    assert claim.subject_text == "cuenta"
    assert claim.predicate.lower() == "fue creada"
    assert "marzo de 2025" in (claim.object_text or "").lower()
    assert claim.claim_type == "event"


def test_claim_extractor_hu_event_uses_temporal_phrase_as_object_not_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("A dokumentum 2026 márciusában frissült.", language="hu")

    claim = claims[0]
    assert claim.subject_text == "dokumentum"
    assert claim.predicate.lower() == "frissült"
    assert "2026" in (claim.object_text or "")


def test_claim_extractor_multi_event_sentence_creates_two_claims() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "The account was created in March 2025 and updated in April 2026.",
        language="en",
    )

    assert len(claims) >= 2
    assert claims[0].subject_text == "account"
    assert claims[0].predicate.lower() == "was created"
    assert "march 2025" in (claims[0].object_text or "").lower()
    assert claims[1].subject_text == "account"
    assert claims[1].predicate.lower() == "updated"
    assert "april 2026" in (claims[1].object_text or "").lower()


def test_claim_extractor_multi_event_spanish_reuses_first_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "La cuenta fue creada en marzo de 2025 y actualizada en abril de 2026.",
        language="es",
    )

    assert len(claims) >= 2
    assert claims[0].subject_text == "cuenta"
    assert claims[0].predicate.lower() == "fue creada"
    assert "marzo de 2025" in (claims[0].object_text or "").lower()
    assert claims[1].subject_text == "cuenta"
    assert claims[1].predicate.lower() == "actualizada"
    assert "abril de 2026" in (claims[1].object_text or "").lower()


def test_claim_extractor_spanish_elliptic_followup_keeps_only_meaningful_claim_after_quality_gate() -> None:
    first_sentence, mentions_a, claims_a, language_a = _extract_claims(
        "La cuenta fue creada en marzo de 2025.",
        language="es",
    )
    second_sentence, mentions_b, claims_b, language_b = _extract_claims(
        "Fue actualizada en abril de 2026.",
        language="es",
    )

    filtered_first = ClaimQualityGate().filter_claims(first_sentence, claims_a, language="es")
    filtered_second = ClaimQualityGate().filter_claims(second_sentence, claims_b, language="es")
    resolved = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": str(first_sentence.id),
                "order_index": 0,
                "text": first_sentence.text_content,
                "language": language_a,
                "mentions": mentions_a,
                "claims": filtered_first,
            },
            {
                "sentence_id": str(second_sentence.id),
                "order_index": 1,
                "text": second_sentence.text_content,
                "language": language_b,
                "mentions": mentions_b,
                "claims": filtered_second,
            },
        ]
    )

    assert len(filtered_first) == 1
    assert len(filtered_second) == 1
    assert filtered_second[0].predicate.lower() == "actualizada"
    assert "abril de 2026" in (filtered_second[0].object_text or "").lower()
    assert filtered_second[0].subject_text == ""

    resolved_second = resolved[1]["claims"][0]
    assert resolved_second.subject_text == "cuenta"
    assert resolved_second.predicate_text.lower() == "actualizada"
    assert "abril de 2026" in (resolved_second.object_text or "").lower()


def test_claim_extractor_drops_uncertainty_noise_sentence() -> None:
    sentence, _mentions, raw_claims, _language = _extract_claims(
        "User login maybe active, not sure conflicting info.",
        language="en",
    )

    claims = ClaimQualityGate().filter_claims(sentence, raw_claims, language="en")

    assert claims == []


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("TODO: ellenőrizni majd később, ez csak note-only content.", "hu"),
        ("Ignore this note-only content.", "en"),
        ("TODO ignorar esto, solo nota.", "es"),
    ],
)
def test_claim_extractor_skips_meta_noise_sentences(text: str, language: str) -> None:
    sentence = Sentence(text_content=text, metadata={"language": language})
    should_process, reason = ClaimQualityGate().should_process_sentence(text, language)
    mentions = MentionExtractor().extract(sentence, language=language)
    claims = ClaimExtractorV1().extract(sentence, mentions, language=language)

    assert should_process is False
    assert reason == "sentence_is_explicit_noise"
    assert claims == []


def test_claim_extractor_hu_temporal_fragment_never_becomes_subject() -> None:
    _sentence, _mentions, claims, _language = _extract_claims("2024- még inaktív volt.", language="hu")

    assert claims == []


@pytest.mark.parametrize(
    ("text", "language", "expected_subject"),
    [
        ("The admin user must enable two-factor authentication.", "en", "admin user"),
        ("Az admin felhasználó kötelező kétfaktoros azonosítást használ.", "hu", "admin felhasználó"),
        ("El usuario administrador debe activar autenticación de dos factores.", "es", "usuario administrador"),
    ],
)
def test_claim_extractor_keeps_admin_user_subjects(text: str, language: str, expected_subject: str) -> None:
    _sentence, _mentions, claims, _language = _extract_claims(text, language=language)

    assert len(claims) == 1
    assert claims[0].subject_text == expected_subject
    assert claims[0].claim_type == "rule_procedure"


def test_claim_extractor_spanish_rule_keeps_sentence_level_language() -> None:
    _sentence, _mentions, claims, language = _extract_claims(
        "El usuario debe aceptar la política de privacidad antes de usar el panel."
    )

    assert language == "es"
    assert claims[0].subject_text == "usuario"
    assert claims[0].predicate.lower() == "debe"
    assert "aceptar la política de privacidad" in (claims[0].object_text or "").lower()


def test_claim_extractor_hu_kiss_marton_vezetoje_user_example() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "Kiss Márton a Zalka 2000 compliance vezetője.",
        language="hu",
    )

    claim = claims[0]
    assert claim.subject_text == "Kiss Márton"
    assert claim.predicate.lower() == "vezetője"
    assert (claim.object_text or "").lower() == "zalka 2000 compliance"
    assert " a " not in f" {claim.subject_text} "
    assert "kiss" not in (claim.object_text or "").lower()


def test_claim_extractor_hu_felelt_korabban_user_example() -> None:
    sentence, _mentions, claims, _language = _extract_claims(
        "Kiss Márton korábban a belső audit folyamatért felelt.",
        language="hu",
    )

    claim = next(c for c in claims if c.predicate.lower() == "felelt")
    assert claim.subject_text == "Kiss Márton"
    assert "belső audit folyamatért" in (claim.object_text or "").lower()
    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu", mentions=_mentions)
    assert frame.time_mode == "bounded"
    assert frame.time_value and "kor" in (frame.time_value or "").lower()


def test_claim_extractor_hu_felelt_keeps_year_out_of_subject_and_person_out_of_object() -> None:
    sentence, mentions, claims, _language = _extract_claims(
        "Kovács Péter 2025-ben még a budapesti onboarding folyamatért felelt.",
        language="hu",
    )

    claim = next(c for c in claims if c.predicate.lower() == "felelt")
    assert claim.subject_text == "Kovács Péter"
    assert claim.object_text == "budapesti onboarding folyamatért"
    assert "2025" not in claim.subject_text
    assert "kovács" not in (claim.object_text or "").lower()
    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu", mentions=mentions)
    assert frame.time_mode == "bounded"
    assert frame.time_value == "2025"
    assert frame.space_value == "budapesti"


def test_claim_extractor_hu_igenyel_jelenleg_keeps_time_out_of_subject_and_object_clean() -> None:
    sentence, mentions, claims, _language = _extract_claims(
        "A login rendszer jelenleg kétfaktoros azonosítást igényel.",
        language="hu",
    )

    claim = next(c for c in claims if c.predicate.lower() == "igényel")
    assert claim.subject_text == "login rendszer"
    assert claim.object_text == "kétfaktoros azonosítást"
    assert "jelenleg" not in claim.subject_text.lower()
    assert "kétfaktoros" not in claim.subject_text.lower()
    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu", mentions=mentions)
    assert frame.time_mode == "current"
    assert frame.time_value == "jelenleg"


def test_claim_extractor_hu_search_module_use_uses_purpose_phrase_in_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "A keresési modul Qdrant indexet használ a profiljelöltek gyors megtalálásához.",
        language="hu",
    )

    claim = claims[0]
    subj = (claim.subject_text or "").lower()
    assert subj == "keresési modul"
    assert "qdrant" not in subj
    assert "indexet" not in subj
    assert "használ" in claim.predicate.lower()
    assert (claim.object_text or "").strip().lower() == "qdrant indexet"
    assert "megtalálás" not in (claim.object_text or "").lower()


def test_claim_extractor_hu_hasznal_pair_same_subject_for_search_module() -> None:
    _s1, _m1, claims_a, _lang = _extract_claims(
        "A keresési modul Qdrant indexet használ a profiljelöltek gyors megtalálásához.",
        language="hu",
    )
    _s2, _m2, claims_b, _lang2 = _extract_claims(
        "A keresési modul OpenAI embeddinget használ.",
        language="hu",
    )
    assert len(claims_a) == 1 and len(claims_b) == 1
    assert claims_a[0].subject_text.lower() == claims_b[0].subject_text.lower() == "keresési modul"
    assert (claims_a[0].object_text or "").strip().lower() == "qdrant indexet"
    assert (claims_b[0].object_text or "").strip() == "OpenAI embeddinget"
    assert claims_b[0].subject_text == "keresési modul"
    for c in (claims_a[0], claims_b[0]):
        assert c.claim_type in {"stable_descriptor", "relation"}
        assert c.claim_type != "other"
        assert float(c.confidence) >= 0.5
        assert fold_text(c.predicate) != "describes"


def test_claim_extractor_en_uses_pair_same_subject_for_search_module() -> None:
    """Visszafelé kompatibilitás: két mondat, ugyanaz a „search module” alany (local resolver: 2 claim)."""
    _s1, _m1, claims_a, _lang = _extract_claims(
        "The search module uses the Qdrant index.",
        language="en",
    )
    _s2, _m2, claims_b, _lang2 = _extract_claims(
        "The search module uses OpenAI embeddings.",
        language="en",
    )
    assert len(claims_a) == 1 and len(claims_b) == 1
    assert claims_a[0].subject_text.lower() == claims_b[0].subject_text.lower() == "search module"
    assert "qdrant" in (claims_a[0].object_text or "").lower()
    assert "openai" in (claims_b[0].object_text or "").lower() and "embedding" in (claims_b[0].object_text or "").lower()
    assert claims_a[0].predicate.lower().startswith("use")
    assert claims_b[0].predicate.lower().startswith("use")
    for c in (claims_a[0], claims_b[0]):
        assert c.claim_type in {"stable_descriptor", "relation"}
        assert float(c.confidence) >= 0.5
        assert fold_text(c.predicate) != "describes"


def test_claim_extractor_es_utiliza_pair_same_subject_for_modulo_busqueda() -> None:
    """Visszafelé kompatibilitás: két mondat, ugyanaz a „módulo de búsqueda” alany (local resolver: 2 claim)."""
    _s1, _m1, claims_a, _lang = _extract_claims(
        "El módulo de búsqueda utiliza el índice Qdrant.",
        language="es",
    )
    _s2, _m2, claims_b, _lang2 = _extract_claims(
        "El módulo de búsqueda utiliza embeddings de OpenAI.",
        language="es",
    )
    assert len(claims_a) == 1 and len(claims_b) == 1

    def _es_subject_ok(text: str) -> bool:
        t = (text or "").lower()
        return "módulo de búsqueda" in t or "modulo de busqueda" in fold_text(text or "")

    assert _es_subject_ok(claims_a[0].subject_text or "")
    assert _es_subject_ok(claims_b[0].subject_text or "")
    assert fold_text(claims_a[0].subject_text or "") == fold_text(claims_b[0].subject_text or "")
    assert "qdrant" in (claims_a[0].object_text or "").lower()
    assert "openai" in (claims_b[0].object_text or "").lower() and "embedding" in (claims_b[0].object_text or "").lower()
    assert claims_a[0].predicate.lower().startswith("utiliza")
    assert claims_b[0].predicate.lower().startswith("utiliza")
    for c in (claims_a[0], claims_b[0]):
        assert c.claim_type in {"stable_descriptor", "relation"}
        assert float(c.confidence) >= 0.5
        assert fold_text(c.predicate) != "describes"


def test_claim_extractor_hu_hasznal_openai_embedding_general_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "A keresési modul OpenAI embeddinget használ.",
        language="hu",
    )
    assert len(claims) == 1
    assert claims[0].subject_text == "keresési modul"
    assert claims[0].predicate.lower() == "használ"
    assert (claims[0].object_text or "").strip() == "OpenAI embeddinget"


def test_claim_extractor_state_drops_duplicate_place_token_object() -> None:
    _sentence, _mentions, claims, _language = _extract_claims(
        "The London office is currently active London.",
        language="en",
    )

    claim = claims[0]
    assert claim.subject_text == "London office"
    assert claim.predicate.lower() == "is currently active"
    assert claim.object_text is None


def test_claim_extractor_en_sarah_miller_responsible() -> None:
    sentence, _mentions, claims, _language = _extract_claims(
        "Sarah Miller was previously responsible for the internal audit process.",
        language="en",
    )

    claim = claims[0]
    assert claim.subject_text == "Sarah Miller"
    assert claim.predicate.lower() == "responsible"
    o = (claim.object_text or "").lower()
    assert "internal audit process" in o
    assert fold_text(claim.object_text) != "previously"
    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="en", mentions=_mentions)
    assert frame.time_mode == "bounded"
    assert frame.time_value and "previous" in (frame.time_value or "").lower()
