from __future__ import annotations

import pytest

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _sentence(text: str, language: str = "en") -> Sentence:
    return Sentence(text_content=text, metadata={"language": language})


def _claim(
    *,
    sentence_id: str,
    subject: str,
    predicate: str,
    object_text: str | None,
    claim_type: str,
    confidence: float = 0.78,
    predicate_found: bool = True,
) -> Claim:
    return Claim(
        sentence_id=sentence_id,
        subject_text=subject,
        predicate_text=predicate,
        object_text=object_text,
        claim_type=claim_type,
        confidence=confidence,
        metadata={"predicate_found": predicate_found},
    )


def test_quality_gate_drops_question_sentences() -> None:
    sentence = _sentence("What does the billing module use?", language="en")
    claims = [
        _claim(
            sentence_id=sentence.id,
            subject="billing module",
            predicate="uses",
            object_text="Stripe",
            claim_type="stable_descriptor",
        )
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert accepted == []


def test_try_sentence_screening_blocks_question_before_extract() -> None:
    sentence = _sentence("What does the billing module use?", language="en")
    gate = ClaimQualityGate()
    diag = gate.try_sentence_screening(sentence, resolved_language="en")
    assert diag is not None
    assert diag.get("skipped") is True
    assert diag.get("sentence_reason") == "sentence_is_question"
    accepted, _ = gate.filter_claims_with_diagnostics(sentence, [], language="en", assume_sentence_prevalidated=True)
    assert accepted == []


def test_quality_gate_drops_describes_and_stopword_subjects() -> None:
    sentence = _sentence("The panel maybe.", language="en")
    claims = [
        _claim(
            sentence_id=sentence.id,
            subject="the",
            predicate="describes",
            object_text="panel",
            claim_type="other",
            confidence=0.4,
            predicate_found=False,
        )
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert accepted == []


def test_quality_gate_keeps_only_top_two_non_event_claims() -> None:
    sentence = _sentence("The account was created and updated, and the panel remains active.", language="en")
    claims = [
        _claim(sentence_id=sentence.id, subject="account", predicate="created", object_text="March 2025", claim_type="event"),
        _claim(sentence_id=sentence.id, subject="account", predicate="updated", object_text="April 2026", claim_type="event"),
        _claim(sentence_id=sentence.id, subject="panel", predicate="active", object_text=None, claim_type="state"),
        _claim(sentence_id=sentence.id, subject="and", predicate="describes", object_text="noise", claim_type="other", confidence=0.3, predicate_found=False),
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert len(accepted) == 2
    assert all(item.claim_type != "other" for item in accepted)


def test_quality_gate_allows_up_to_three_events() -> None:
    sentence = _sentence("The account was created, updated, and deprecated.", language="en")
    claims = [
        _claim(sentence_id=sentence.id, subject="account", predicate="created", object_text="March 2025", claim_type="event"),
        _claim(sentence_id=sentence.id, subject="account", predicate="updated", object_text="April 2026", claim_type="event"),
        _claim(sentence_id=sentence.id, subject="account", predicate="deprecated", object_text="May 2027", claim_type="event"),
        _claim(sentence_id=sentence.id, subject="account", predicate="describes", object_text="noise", claim_type="other", confidence=0.3, predicate_found=False),
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert len(accepted) == 3
    assert all(item.claim_type == "event" for item in accepted)


def test_quality_gate_drops_uncertainty_claims() -> None:
    sentence = _sentence("User login maybe active, not sure conflicting info.", language="en")
    claims = [
        _claim(
            sentence_id=sentence.id,
            subject="user login maybe",
            predicate="active",
            object_text="not sure conflicting info",
            claim_type="state",
        )
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert accepted == []


def test_quality_gate_drops_fragment_marker_sentence() -> None:
    sentence = _sentence("partial sentence active", language="en")
    claims = [
        _claim(
            sentence_id=sentence.id,
            subject="partial sentence",
            predicate="active",
            object_text=None,
            claim_type="state",
        )
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert accepted == []


def test_quality_gate_drops_repetition_noise_sentence() -> None:
    sentence = _sentence("Stripe Stripe active", language="en")
    claims = [
        _claim(
            sentence_id=sentence.id,
            subject="Stripe Stripe",
            predicate="active",
            object_text=None,
            claim_type="state",
        )
    ]

    accepted = ClaimQualityGate().filter_claims(sentence, claims, language="en")

    assert accepted == []


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Ez csak zaj, nem kell belőle fontos claim.", "hu"),
        ("Csak claim extraction / sanitizer javítás kell.", "hu"),
        ("Teszteljük, hogy működik-e.", "hu"),
        ("Ignore this line.", "en"),
    ],
)
def test_try_sentence_screening_blocks_explicit_noise_and_meta_sentences(text: str, language: str) -> None:
    sentence = _sentence(text, language=language)

    diagnostics = ClaimQualityGate().try_sentence_screening(sentence, resolved_language=language)

    assert diagnostics is not None
    assert diagnostics.get("skipped") is True
    assert diagnostics.get("sentence_reason") == "sentence_is_explicit_noise"


def test_quality_gate_drops_claim_from_meta_sentence_after_diagnostics() -> None:
    sentence = _sentence("Ignore this line.", language="en")
    claims = [
        _claim(
            sentence_id=sentence.id,
            subject="line",
            predicate="describes",
            object_text="ignore marker",
            claim_type="other",
            predicate_found=False,
        )
    ]

    accepted, diagnostics = ClaimQualityGate().filter_claims_with_diagnostics(sentence, claims, language="en")

    assert accepted == []
    assert diagnostics["skipped"] is True
    assert diagnostics["sentence_reason"] == "sentence_is_explicit_noise"
