from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.candidate_consolidator import merge_or_split_adjacent_candidates
from apps.knowledge.service.claim_split.types import ClaimCandidate, ParsedDoc, ParsedToken


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _token(
    *,
    text: str,
    idx: int,
    char_start: int,
) -> ParsedToken:
    return ParsedToken(
        text=text,
        lemma=text.lower(),
        pos="X",
        dep="dep",
        idx=idx,
        head_idx=None,
        char_start=char_start,
        char_end=char_start + len(text),
    )


def _candidate(
    *,
    text: str,
    subject_hint: str | None,
    predicate_hint: str | None,
    start_token: int,
    end_token: int,
) -> ClaimCandidate:
    return ClaimCandidate(
        text_span=text,
        subject_hint=subject_hint,
        predicate_hint=predicate_hint,
        object_hint=None,
        start_token=start_token,
        end_token=end_token,
        char_start=0,
        char_end=len(text),
        confidence=0.7,
        split_reason=["test"],
    )


def test_merge_or_split_adjacent_candidates_merges_same_subject_with_and_connector() -> None:
    doc = ParsedDoc(
        text="A rendszer gyors és stabil.",
        tokens=[
            _token(text="A", idx=0, char_start=0),
            _token(text="rendszer", idx=1, char_start=2),
            _token(text="gyors", idx=2, char_start=11),
            _token(text="és", idx=3, char_start=17),
            _token(text="stabil", idx=4, char_start=20),
            _token(text=".", idx=5, char_start=26),
        ],
    )
    candidates = [
        _candidate(text="A rendszer gyors", subject_hint="rendszer", predicate_hint="gyors", start_token=0, end_token=3),
        _candidate(text="stabil", subject_hint="rendszer", predicate_hint="stabil", start_token=4, end_token=5),
    ]

    merged = merge_or_split_adjacent_candidates(candidates, doc)

    assert len(merged) == 1
    assert merged[0].text_span == "A rendszer gyors és stabil"


def test_merge_or_split_adjacent_candidates_does_not_merge_across_sentence_boundary() -> None:
    doc = ParsedDoc(
        text="A rendszer gyors. A rendszer biztonságos.",
        tokens=[
            _token(text="A", idx=0, char_start=0),
            _token(text="rendszer", idx=1, char_start=2),
            _token(text="gyors", idx=2, char_start=11),
            _token(text=".", idx=3, char_start=16),
            _token(text="A", idx=4, char_start=18),
            _token(text="rendszer", idx=5, char_start=20),
            _token(text="biztonságos", idx=6, char_start=29),
            _token(text=".", idx=7, char_start=40),
        ],
    )
    candidates = [
        _candidate(text="A rendszer gyors.", subject_hint="rendszer", predicate_hint="gyors", start_token=0, end_token=4),
        _candidate(text="A rendszer biztonságos.", subject_hint="rendszer", predicate_hint="biztonságos", start_token=4, end_token=8),
    ]

    merged = merge_or_split_adjacent_candidates(candidates, doc)

    assert len(merged) == 2


def test_merge_or_split_adjacent_candidates_does_not_merge_when_gap_is_not_connector_sequence() -> None:
    doc = ParsedDoc(
        text="A rendszer gyors ezért stabil.",
        tokens=[
            _token(text="A", idx=0, char_start=0),
            _token(text="rendszer", idx=1, char_start=2),
            _token(text="gyors", idx=2, char_start=11),
            _token(text="ezért", idx=3, char_start=17),
            _token(text="stabil", idx=4, char_start=23),
            _token(text=".", idx=5, char_start=29),
        ],
    )
    candidates = [
        _candidate(text="A rendszer gyors", subject_hint="rendszer", predicate_hint="gyors", start_token=0, end_token=3),
        _candidate(text="stabil", subject_hint="rendszer", predicate_hint="stabil", start_token=4, end_token=5),
    ]

    merged = merge_or_split_adjacent_candidates(candidates, doc)

    assert len(merged) == 2
