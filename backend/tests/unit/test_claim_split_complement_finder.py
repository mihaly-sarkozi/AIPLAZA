from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.complement_finder import find_local_complements
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


def test_find_local_complements_keeps_direct_object_child() -> None:
    doc = ParsedDoc(
        text="A biztosító díjat fizet.",
        tokens=[
            _token(text="A", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="biztosító", idx=1, pos="NOUN", dep="nsubj", head_idx=3, char_start=2),
            _token(text="díjat", idx=2, pos="NOUN", dep="obj", head_idx=3, char_start=12),
            _token(text="fizet", idx=3, pos="VERB", dep="root", head_idx=None, char_start=18),
            _token(text=".", idx=4, pos="PUNCT", dep="punct", head_idx=3, char_start=23),
        ],
    )

    hints = find_local_complements(doc.tokens[3], doc)

    assert [token.text for token in hints.objects] == ["díjat"]


def test_find_local_complements_keeps_subtree_attribute_of_predicate_object() -> None:
    doc = ParsedDoc(
        text="A biztosító kárösszeget részletekben fizet.",
        tokens=[
            _token(text="A", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="biztosító", idx=1, pos="NOUN", dep="nsubj", head_idx=4, char_start=2),
            _token(text="kárösszeget", idx=2, pos="NOUN", dep="obj", head_idx=4, char_start=12),
            _token(text="részletekben", idx=3, pos="NOUN", dep="obl", head_idx=2, char_start=22),
            _token(text="fizet", idx=4, pos="VERB", dep="root", head_idx=None, char_start=35),
            _token(text=".", idx=5, pos="PUNCT", dep="punct", head_idx=4, char_start=40),
        ],
    )

    hints = find_local_complements(doc.tokens[4], doc)

    assert [token.text for token in hints.objects] == ["kárösszeget", "részletekben"]


def test_find_local_complements_excludes_later_clause_object_from_conj_branch() -> None:
    doc = ParsedDoc(
        text="A biztosító fizet, és a szerződő díjat visel.",
        tokens=[
            _token(text="A", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="biztosító", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=2),
            _token(text="fizet", idx=2, pos="VERB", dep="root", head_idx=None, char_start=12),
            _token(text=",", idx=3, pos="PUNCT", dep="punct", head_idx=2, char_start=17),
            _token(text="és", idx=4, pos="CCONJ", dep="cc", head_idx=8, char_start=19),
            _token(text="a", idx=5, pos="DET", dep="det", head_idx=6, char_start=22),
            _token(text="szerződő", idx=6, pos="NOUN", dep="nsubj", head_idx=8, char_start=24),
            _token(text="díjat", idx=7, pos="NOUN", dep="obj", head_idx=8, char_start=33),
            _token(text="visel", idx=8, pos="VERB", dep="conj", head_idx=2, char_start=39),
            _token(text=".", idx=9, pos="PUNCT", dep="punct", head_idx=8, char_start=44),
        ],
    )

    hints = find_local_complements(doc.tokens[2], doc)

    assert [token.text for token in hints.objects] == []


def test_find_local_complements_excludes_english_ccomp_clause_head() -> None:
    doc = ParsedDoc(
        text="The policy states that the answer is fast.",
        tokens=[
            _token(text="The", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="policy", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=4),
            _token(text="states", idx=2, pos="VERB", dep="root", head_idx=None, char_start=11),
            _token(text="that", idx=3, pos="SCONJ", dep="mark", head_idx=7, char_start=18),
            _token(text="the", idx=4, pos="DET", dep="det", head_idx=5, char_start=23),
            _token(text="answer", idx=5, pos="NOUN", dep="nsubj", head_idx=7, char_start=27),
            _token(text="is", idx=6, pos="AUX", dep="cop", head_idx=7, char_start=34),
            _token(text="fast", idx=7, pos="ADJ", dep="ccomp", head_idx=2, char_start=37),
            _token(text=".", idx=8, pos="PUNCT", dep="punct", head_idx=2, char_start=41),
        ],
        language_tag="en",
    )

    hints = find_local_complements(doc.tokens[2], doc)

    assert [token.text for token in hints.objects] == []
    assert [token.text for token in hints.attributes] == []


def test_find_local_complements_excludes_spanish_advcl_clause_head() -> None:
    doc = ParsedDoc(
        text="La poliza paga cuando el sistema responde rapido.",
        tokens=[
            _token(text="La", idx=0, pos="DET", dep="det", head_idx=1, char_start=0),
            _token(text="poliza", idx=1, pos="NOUN", dep="nsubj", head_idx=2, char_start=3),
            _token(text="paga", idx=2, pos="VERB", dep="root", head_idx=None, char_start=10),
            _token(text="cuando", idx=3, pos="SCONJ", dep="mark", head_idx=6, char_start=15),
            _token(text="el", idx=4, pos="DET", dep="det", head_idx=5, char_start=22),
            _token(text="sistema", idx=5, pos="NOUN", dep="nsubj", head_idx=6, char_start=25),
            _token(text="responde", idx=6, pos="VERB", dep="advcl", head_idx=2, char_start=33),
            _token(text="rapido", idx=7, pos="ADV", dep="advmod", head_idx=6, char_start=42),
            _token(text=".", idx=8, pos="PUNCT", dep="punct", head_idx=2, char_start=48),
        ],
        language_tag="es",
    )

    hints = find_local_complements(doc.tokens[2], doc)

    assert [token.text for token in hints.objects] == []
    assert [token.text for token in hints.attributes] == []
    assert [token.text for token in hints.modifiers] == []
