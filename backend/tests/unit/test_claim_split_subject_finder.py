from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.subject_finder import find_best_subject
from apps.knowledge.service.claim_split.types import ParsedDoc, ParsedToken


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


def test_find_best_subject_fallback_stays_within_sentence_boundary() -> None:
    doc = ParsedDoc(
        text="Az ég kék. A fű zöld.",
        tokens=[
            _token(text="Az", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="ég", idx=1, pos="NOUN", dep="dep", head_idx=2, char_start=3),
            _token(text="kék", idx=2, pos="ADJ", dep="root", head_idx=None, char_start=6),
            _token(text=".", idx=3, pos="PUNCT", dep="punct", head_idx=2, char_start=9),
            _token(text="A", idx=4, pos="DET", dep="det", head_idx=5, char_start=11),
            _token(text="fű", idx=5, pos="NOUN", dep="dep", head_idx=6, char_start=13),
            _token(text="zöld", idx=6, pos="ADJ", dep="root", head_idx=None, char_start=17),
            _token(text=".", idx=7, pos="PUNCT", dep="punct", head_idx=6, char_start=21),
        ],
    )

    subject = find_best_subject(doc.tokens[6], doc)

    assert subject is not None
    assert subject.text == "fű"


def test_find_best_subject_fallback_ignores_object_like_noun_when_subject_is_available() -> None:
    doc = ParsedDoc(
        text="A biztosító díjat fizet.",
        tokens=[
            _token(text="A", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="biztosító", idx=1, pos="NOUN", dep="dep", head_idx=3, char_start=2),
            _token(text="díjat", idx=2, pos="NOUN", dep="obj", head_idx=3, char_start=12),
            _token(text="fizet", idx=3, pos="VERB", dep="root", head_idx=None, char_start=18),
            _token(text=".", idx=4, pos="PUNCT", dep="punct", head_idx=3, char_start=23),
        ],
    )

    subject = find_best_subject(doc.tokens[3], doc)

    assert subject is not None
    assert subject.text == "biztosító"


def test_find_best_subject_fallback_respects_local_window() -> None:
    tokens = [
        _token(text="Szerződés", idx=0, pos="NOUN", dep="dep", head_idx=13, char_start=0),
    ]
    for idx in range(1, 13):
        tokens.append(
            _token(
                text=f"x{idx}",
                idx=idx,
                pos="ADV",
                dep="advmod",
                head_idx=13,
                char_start=idx * 3,
            )
        )
    tokens.append(_token(text="érvényes", idx=13, pos="ADJ", dep="root", head_idx=None, char_start=40))
    doc = ParsedDoc(text="placeholder", tokens=tokens)

    subject = find_best_subject(doc.tokens[13], doc)

    assert subject is None


def test_find_best_subject_fallback_keeps_english_local_subject_chain() -> None:
    doc = ParsedDoc(
        text="The system works and the answer is fast.",
        tokens=[
            _token(text="The", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="system", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=4),
            _token(text="works", idx=2, pos="VERB", dep="root", head_idx=None, char_start=11),
            _token(text="and", idx=3, pos="CCONJ", dep="cc", head_idx=7, char_start=17),
            _token(text="the", idx=4, pos="DET", dep="det", head_idx=5, char_start=21),
            _token(text="answer", idx=5, pos="NOUN", dep="dep", head_idx=6, char_start=25),
            _token(text="is", idx=6, pos="AUX", dep="cop", head_idx=7, char_start=32),
            _token(text="fast", idx=7, pos="ADJ", dep="root", head_idx=None, char_start=35),
            _token(text=".", idx=8, pos="PUNCT", dep="punct", head_idx=7, char_start=39),
        ],
        language_tag="en",
    )

    subject = find_best_subject(doc.tokens[7], doc)

    assert subject is not None
    assert subject.text == "answer"


def test_find_best_subject_fallback_keeps_spanish_local_subject_chain() -> None:
    doc = ParsedDoc(
        text="El sistema funciona y la respuesta es rapida.",
        tokens=[
            _token(text="El", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="sistema", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=3),
            _token(text="funciona", idx=2, pos="VERB", dep="root", head_idx=None, char_start=11),
            _token(text="y", idx=3, pos="CCONJ", dep="cc", head_idx=7, char_start=20),
            _token(text="la", idx=4, pos="DET", dep="det", head_idx=5, char_start=22),
            _token(text="respuesta", idx=5, pos="NOUN", dep="dep", head_idx=6, char_start=25),
            _token(text="es", idx=6, pos="AUX", dep="cop", head_idx=7, char_start=35),
            _token(text="rapida", idx=7, pos="ADJ", dep="root", head_idx=None, char_start=38),
            _token(text=".", idx=8, pos="PUNCT", dep="punct", head_idx=7, char_start=44),
        ],
        language_tag="es",
    )

    subject = find_best_subject(doc.tokens[7], doc)

    assert subject is not None
    assert subject.text == "respuesta"


def test_find_best_subject_fallback_skips_unattached_english_prior_noun() -> None:
    doc = ParsedDoc(
        text="The system works. Policy text answer fast.",
        tokens=[
            _token(text="The", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="system", idx=1, pos="NOUN", dep="dep", head_idx=2, char_start=4),
            _token(text="works", idx=2, pos="VERB", dep="root", head_idx=None, char_start=11),
            _token(text=".", idx=3, pos="PUNCT", dep="punct", head_idx=2, char_start=16),
            _token(text="Policy", idx=4, pos="NOUN", dep="dep", head_idx=5, char_start=18),
            _token(text="text", idx=5, pos="NOUN", dep="dep", head_idx=6, char_start=25),
            _token(text="answer", idx=6, pos="NOUN", dep="dep", head_idx=None, char_start=30),
            _token(text="fast", idx=7, pos="ADJ", dep="root", head_idx=None, char_start=37),
            _token(text=".", idx=8, pos="PUNCT", dep="punct", head_idx=7, char_start=41),
        ],
        language_tag="en",
    )

    subject = find_best_subject(doc.tokens[7], doc)

    assert subject is None


def test_find_best_subject_spanish_pro_drop_keeps_none_for_bare_verb() -> None:
    doc = ParsedDoc(
        text="Funciona bien.",
        tokens=[
            _token(text="Funciona", idx=0, pos="VERB", dep="root", head_idx=None, char_start=0),
            _token(text="bien", idx=1, pos="ADV", dep="advmod", head_idx=0, char_start=9),
            _token(text=".", idx=2, pos="PUNCT", dep="punct", head_idx=0, char_start=13),
        ],
        language_tag="es",
    )

    subject = find_best_subject(doc.tokens[0], doc)

    assert subject is None


def test_find_best_subject_spanish_pro_drop_skips_noisy_nominal_fallback_for_verb() -> None:
    doc = ParsedDoc(
        text="Segun la poliza puede cambiar.",
        tokens=[
            _token(text="Segun", idx=0, pos="ADP", dep="case", head_idx=2, char_start=0),
            _token(text="la", idx=1, pos="DET", dep="det", head_idx=2, char_start=6),
            _token(text="poliza", idx=2, pos="NOUN", dep="dep", head_idx=4, char_start=9),
            _token(text="puede", idx=3, pos="AUX", dep="aux", head_idx=4, char_start=16),
            _token(text="cambiar", idx=4, pos="VERB", dep="root", head_idx=None, char_start=22),
            _token(text=".", idx=5, pos="PUNCT", dep="punct", head_idx=4, char_start=29),
        ],
        language_tag="es",
    )

    subject = find_best_subject(doc.tokens[4], doc)

    assert subject is None


def test_find_best_subject_spanish_pro_drop_skips_noisy_nominal_fallback_for_adjective() -> None:
    doc = ParsedDoc(
        text="Segun la poliza es obligatorio.",
        tokens=[
            _token(text="Segun", idx=0, pos="ADP", dep="case", head_idx=2, char_start=0),
            _token(text="la", idx=1, pos="DET", dep="det", head_idx=2, char_start=6),
            _token(text="poliza", idx=2, pos="NOUN", dep="dep", head_idx=3, char_start=9),
            _token(text="es", idx=3, pos="AUX", dep="cop", head_idx=4, char_start=16),
            _token(text="obligatorio", idx=4, pos="ADJ", dep="root", head_idx=None, char_start=19),
            _token(text=".", idx=5, pos="PUNCT", dep="punct", head_idx=4, char_start=30),
        ],
        language_tag="es",
    )

    subject = find_best_subject(doc.tokens[4], doc)

    assert subject is None
