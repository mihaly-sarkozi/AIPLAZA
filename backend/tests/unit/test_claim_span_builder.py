from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.claim_span_builder import build_claim_span
from apps.knowledge.service.claim_split.types import ComplementHints, ParsedDoc, ParsedToken


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _token(
    *,
    text: str,
    idx: int,
    pos: str,
    dep: str,
    head_idx: int | None,
    char_start: int,
) -> ParsedToken:
    return ParsedToken(
        text=text,
        lemma=text.lower(),
        pos=pos,
        dep=dep,
        idx=idx,
        head_idx=head_idx,
        char_start=char_start,
        char_end=char_start + len(text),
    )


def test_build_claim_span_expands_local_phrase_attachments() -> None:
    doc = ParsedDoc(
        text="A biztosító a díjat megfizeti.",
        tokens=[
            _token(text="A", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="biztosító", idx=1, pos="NOUN", dep="nsubj", head_idx=4, char_start=2),
            _token(text="a", idx=2, pos="DET", dep="det", head_idx=3, char_start=12),
            _token(text="díjat", idx=3, pos="NOUN", dep="obj", head_idx=4, char_start=14),
            _token(text="megfizeti", idx=4, pos="VERB", dep="root", head_idx=None, char_start=20),
            _token(text=".", idx=5, pos="PUNCT", dep="punct", head_idx=4, char_start=29),
        ],
    )

    span = build_claim_span(
        predicate=doc.tokens[4],
        subject=doc.tokens[1],
        complements=ComplementHints(objects=[doc.tokens[3]]),
        doc=doc,
    )

    assert span.text(doc) == "A biztosító a díjat megfizeti"


def test_build_claim_span_clips_before_next_clause_boundary() -> None:
    doc = ParsedDoc(
        text="A biztosító fizet, és a szerződő értesít.",
        tokens=[
            _token(text="A", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="biztosító", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=2),
            _token(text="fizet", idx=2, pos="VERB", dep="root", head_idx=None, char_start=12),
            _token(text=",", idx=3, pos="PUNCT", dep="punct", head_idx=2, char_start=17),
            _token(text="és", idx=4, pos="CCONJ", dep="cc", head_idx=7, char_start=19),
            _token(text="a", idx=5, pos="DET", dep="det", head_idx=6, char_start=22),
            _token(text="szerződő", idx=6, pos="NOUN", dep="nsubj", head_idx=7, char_start=24),
            _token(text="értesít", idx=7, pos="VERB", dep="conj", head_idx=2, char_start=33),
            _token(text=".", idx=8, pos="PUNCT", dep="punct", head_idx=7, char_start=40),
        ],
    )

    span = build_claim_span(
        predicate=doc.tokens[2],
        subject=doc.tokens[1],
        complements=ComplementHints(),
        doc=doc,
    )

    assert span.text(doc) == "A biztosító fizet"


def test_build_claim_span_does_not_expand_past_sentence_boundary() -> None:
    doc = ParsedDoc(
        text="Az ég kék. A fű zöld.",
        tokens=[
            _token(text="Az", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="ég", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=3),
            _token(text="kék", idx=2, pos="ADJ", dep="root", head_idx=None, char_start=6),
            _token(text=".", idx=3, pos="PUNCT", dep="punct", head_idx=2, char_start=9),
            _token(text="A", idx=4, pos="DET", dep="det", head_idx=5, char_start=11),
            _token(text="fű", idx=5, pos="NOUN", dep="nsubj", head_idx=6, char_start=13),
            _token(text="zöld", idx=6, pos="ADJ", dep="root", head_idx=None, char_start=17),
            _token(text=".", idx=7, pos="PUNCT", dep="punct", head_idx=6, char_start=21),
        ],
    )

    span = build_claim_span(
        predicate=doc.tokens[6],
        subject=doc.tokens[5],
        complements=ComplementHints(),
        doc=doc,
    )

    assert span.text(doc) == "A fű zöld."


def test_build_claim_span_skips_detached_english_parenthetical_anchors() -> None:
    doc = ParsedDoc(
        text="The system, after a long review, works well and remains stable.",
        tokens=[
            _token(text="The", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="system", idx=1, pos="NOUN", dep="nsubj", head_idx=7, char_start=4),
            _token(text=",", idx=2, pos="PUNCT", dep="punct", head_idx=7, char_start=10),
            _token(text="after", idx=3, pos="ADP", dep="case", head_idx=6, char_start=12),
            _token(text="a", idx=4, pos="DET", dep="det", head_idx=6, char_start=18),
            _token(text="long", idx=5, pos="ADJ", dep="amod", head_idx=6, char_start=20),
            _token(text="review", idx=6, pos="NOUN", dep="obl", head_idx=7, char_start=25),
            _token(text=",", idx=7, pos="PUNCT", dep="punct", head_idx=8, char_start=31),
            _token(text="works", idx=8, pos="VERB", dep="root", head_idx=None, char_start=33),
            _token(text="well", idx=9, pos="ADV", dep="advmod", head_idx=8, char_start=39),
            _token(text="and", idx=10, pos="CCONJ", dep="cc", head_idx=11, char_start=44),
            _token(text="remains", idx=11, pos="VERB", dep="conj", head_idx=8, char_start=48),
            _token(text="stable", idx=12, pos="ADJ", dep="xcomp", head_idx=11, char_start=56),
            _token(text=".", idx=13, pos="PUNCT", dep="punct", head_idx=8, char_start=62),
        ],
        language_tag="en",
    )

    span = build_claim_span(
        predicate=doc.tokens[8],
        subject=doc.tokens[1],
        complements=ComplementHints(objects=[doc.tokens[6]], attributes=[doc.tokens[9]]),
        doc=doc,
    )

    assert span.text(doc) == "works well"


def test_build_claim_span_skips_detached_spanish_parenthetical_anchors() -> None:
    doc = ParsedDoc(
        text="El sistema, despues de una revision extensa, funciona bien y sigue estable.",
        tokens=[
            _token(text="El", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="sistema", idx=1, pos="NOUN", dep="nsubj", head_idx=8, char_start=3),
            _token(text=",", idx=2, pos="PUNCT", dep="punct", head_idx=8, char_start=10),
            _token(text="despues", idx=3, pos="ADV", dep="advmod", head_idx=6, char_start=12),
            _token(text="de", idx=4, pos="ADP", dep="case", head_idx=6, char_start=20),
            _token(text="una", idx=5, pos="DET", dep="det", head_idx=6, char_start=23),
            _token(text="revision", idx=6, pos="NOUN", dep="obl", head_idx=8, char_start=27),
            _token(text="extensa", idx=7, pos="ADJ", dep="amod", head_idx=6, char_start=36),
            _token(text=",", idx=8, pos="PUNCT", dep="punct", head_idx=9, char_start=43),
            _token(text="funciona", idx=9, pos="VERB", dep="root", head_idx=None, char_start=45),
            _token(text="bien", idx=10, pos="ADV", dep="advmod", head_idx=9, char_start=54),
            _token(text="y", idx=11, pos="CCONJ", dep="cc", head_idx=12, char_start=59),
            _token(text="sigue", idx=12, pos="VERB", dep="conj", head_idx=9, char_start=61),
            _token(text="estable", idx=13, pos="ADJ", dep="xcomp", head_idx=12, char_start=67),
            _token(text=".", idx=14, pos="PUNCT", dep="punct", head_idx=9, char_start=74),
        ],
        language_tag="es",
    )

    span = build_claim_span(
        predicate=doc.tokens[9],
        subject=doc.tokens[1],
        complements=ComplementHints(objects=[doc.tokens[6]], attributes=[doc.tokens[10]]),
        doc=doc,
    )

    assert span.text(doc) == "funciona bien"
