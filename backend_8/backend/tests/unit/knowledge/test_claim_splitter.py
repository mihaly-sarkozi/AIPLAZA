from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.types import ClaimCandidate
from apps.knowledge.service.claim_splitter import MAX_CLAIM_SEGMENTS, ClaimSplitter, split_candidates, split_sentence

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_split_en_created_updated_carryover_subject() -> None:
    s = "The account was created in March 2025 and updated in April 2026."
    segs = ClaimSplitter().split_sentence(s, "en")
    assert len(segs) == 2
    assert "account" in segs[0].lower()
    assert "was created" in segs[0].lower()
    assert "march 2025" in segs[0].lower()
    assert segs[1].lower().startswith("the account updated")
    assert "april 2026" in segs[1].lower()


def test_split_es_creada_actualizada() -> None:
    s = "La cuenta fue creada en enero de 2025 y actualizada en mayo de 2026."
    segs = split_sentence(s, "es")
    assert len(segs) == 2
    assert "fue creada" in segs[0].lower()
    assert "enero de 2025" in segs[0].lower()
    assert segs[1].lower().startswith("la cuenta actualizada")
    assert "mayo de 2026" in segs[1].lower()


def test_split_en_state_but_replaces_it() -> None:
    s = "The London office is currently active, but it was inactive before February 2025."
    segs = ClaimSplitter().split_sentence(s, "en")
    assert len(segs) == 2
    assert "london office" in segs[0].lower()
    assert "is currently active" in segs[0].lower()
    assert "it was" not in segs[1].lower()
    assert "london office" in segs[1].lower()
    assert "inactive" in segs[1].lower()


def test_split_es_state_pero_carryover() -> None:
    s = "La oficina de Madrid está actualmente activa, pero estaba inactiva antes de febrero de 2025."
    segs = ClaimSplitter().split_sentence(s, "es")
    assert len(segs) == 2
    assert "madrid" in segs[0].lower()
    assert "pero" not in segs[0].lower()
    assert "oficina de madrid" in segs[1].lower()
    assert "estaba inactiva" in segs[1].lower()


def test_split_no_pattern_returns_single() -> None:
    s = "The login system uses two-factor authentication."
    assert ClaimSplitter().split_sentence(s, "en") == [s]


def test_split_max_segments_cap() -> None:
    assert MAX_CLAIM_SEGMENTS == 3
    sp = ClaimSplitter(max_segments=1)
    s = "The account was created in March 2025 and updated in April 2026."
    assert len(sp.split_sentence(s, "en")) == 1


def test_split_candidates_dedupes_text_span() -> None:
    c = ClaimCandidate(
        text_span="The account was created in March 2025 and updated in April 2026.",
        subject_hint=None,
        predicate_hint=None,
        object_hint=None,
        start_token=0,
        end_token=1,
        char_start=0,
        char_end=80,
        confidence=0.9,
        split_reason=[],
    )
    out = split_candidates([c], c.text_span, "en")
    assert len(out) == 2
    assert out[0].text_span != out[1].text_span
    assert "claim_splitter_seg_" in ",".join(out[1].split_reason)
