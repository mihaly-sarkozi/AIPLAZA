from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.predicate_finder import find_predicate_heads
from apps.knowledge.service.claim_split.types import ParsedDoc, ParsedToken


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _token(
    *,
    text: str,
    lemma: str,
    idx: int,
    pos: str,
    dep: str,
    head_idx: int | None,
    char_start: int,
) -> ParsedToken:
    return ParsedToken(
        text=text,
        lemma=lemma,
        pos=pos,
        dep=dep,
        idx=idx,
        head_idx=head_idx,
        char_start=char_start,
        char_end=char_start + len(text),
    )


def test_find_predicate_heads_keeps_finite_verbs_and_adjective_roots() -> None:
    doc = ParsedDoc(
        text="A szabály alkalmazandó és a biztosító fizet.",
        tokens=[
            _token(text="A", lemma="a", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="szabály", lemma="szabály", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=2),
            _token(text="alkalmazandó", lemma="alkalmazandó", idx=2, pos="ADJ", dep="ROOT", head_idx=None, char_start=9),
            _token(text="és", lemma="és", idx=3, pos="CCONJ", dep="cc", head_idx=5, char_start=22),
            _token(text="a", lemma="a", idx=4, pos="DET", dep="det", head_idx=5, char_start=25),
            _token(text="biztosító", lemma="biztosító", idx=5, pos="NOUN", dep="nsubj", head_idx=6, char_start=27),
            _token(text="fizet", lemma="fizet", idx=6, pos="VERB", dep="conj", head_idx=2, char_start=37),
        ],
    )

    predicates = find_predicate_heads(doc)

    assert [token.text for token in predicates] == ["alkalmazandó", "fizet"]


def test_find_predicate_heads_keeps_copula_candidates() -> None:
    doc = ParsedDoc(
        text="A szerződés érvényes lesz.",
        tokens=[
            _token(text="A", lemma="a", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="szerződés", lemma="szerződés", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=2),
            _token(text="érvényes", lemma="érvényes", idx=2, pos="ADJ", dep="ROOT", head_idx=None, char_start=12),
            _token(text="lesz", lemma="lesz", idx=3, pos="AUX", dep="cop", head_idx=2, char_start=21),
        ],
    )

    predicates = find_predicate_heads(doc)

    assert [token.text for token in predicates] == ["érvényes", "lesz"]


def test_find_predicate_heads_does_not_treat_policy_like_nouns_as_predicates() -> None:
    doc = ParsedDoc(
        text="A tilos szabály külön figyelmet kap.",
        tokens=[
            _token(text="A", lemma="a", idx=0, pos="DET", dep="det", head_idx=2, char_start=0),
            _token(text="tilos", lemma="tilos", idx=1, pos="NOUN", dep="compound", head_idx=2, char_start=2),
            _token(text="szabály", lemma="szabály", idx=2, pos="NOUN", dep="nsubj", head_idx=5, char_start=8),
            _token(text="külön", lemma="külön", idx=3, pos="ADV", dep="advmod", head_idx=4, char_start=15),
            _token(text="figyelmet", lemma="figyelem", idx=4, pos="NOUN", dep="obj", head_idx=5, char_start=21),
            _token(text="kap", lemma="kap", idx=5, pos="VERB", dep="ROOT", head_idx=None, char_start=31),
        ],
    )

    predicates = find_predicate_heads(doc)

    assert [token.text for token in predicates] == ["kap"]


def test_find_predicate_heads_uses_english_policy_lexicon() -> None:
    doc = ParsedDoc(
        text="The user must comply.",
        tokens=[
            _token(text="The", lemma="the", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="user", lemma="user", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=4),
            _token(text="must", lemma="must", idx=2, pos="AUX", dep="aux", head_idx=3, char_start=9),
            _token(text="comply", lemma="comply", idx=3, pos="VERB", dep="ROOT", head_idx=None, char_start=14),
        ],
        language_tag="en",
    )

    predicates = find_predicate_heads(doc)

    assert [token.text for token in predicates] == ["must", "comply"]


def test_find_predicate_heads_uses_spanish_policy_lexicon() -> None:
    doc = ParsedDoc(
        text="El sistema debe registrar.",
        tokens=[
            _token(text="El", lemma="el", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="sistema", lemma="sistema", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=3),
            _token(text="debe", lemma="debe", idx=2, pos="AUX", dep="aux", head_idx=3, char_start=11),
            _token(text="registrar", lemma="registrar", idx=3, pos="VERB", dep="ROOT", head_idx=None, char_start=16),
        ],
        language_tag="es",
    )

    predicates = find_predicate_heads(doc)

    assert [token.text for token in predicates] == ["debe", "registrar"]
