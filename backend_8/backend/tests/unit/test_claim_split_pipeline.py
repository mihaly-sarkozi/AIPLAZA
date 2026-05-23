from __future__ import annotations

import pytest

from apps.knowledge.service.claim_split.pipeline import _normalize_morph, _stanza_doc_to_parsed, RegexNlpPipeline


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _MorphObject:
    def to_dict(self) -> dict[str, object]:
        return {
            "Case": "Nom",
            "Number": ["Sing"],
            "Person": ("3",),
            "Empty": "",
            "Missing": None,
        }


def test_normalize_morph_accepts_to_dict_objects() -> None:
    assert _normalize_morph(_MorphObject()) == {
        "Case": "Nom",
        "Number": "Sing",
        "Person": "3",
    }


def test_normalize_morph_accepts_ud_feature_strings() -> None:
    assert _normalize_morph("Case=Nom|Number=Sing|Person=3") == {
        "Case": "Nom",
        "Number": "Sing",
        "Person": "3",
    }


def test_normalize_morph_ignores_invalid_string_parts() -> None:
    assert _normalize_morph("Case=Nom|Broken|Number=Sing") == {
        "Case": "Nom",
        "Number": "Sing",
    }


class _FakeWord:
    def __init__(self, *, text: str, idx: int, head: int, upos: str, deprel: str) -> None:
        self.text = text
        self.id = idx
        self.head = head
        self.upos = upos
        self.deprel = deprel
        self.lemma = text.lower()
        self.feats = None


class _FakeToken:
    def __init__(self, *, text: str, start_char: int, end_char: int, word: _FakeWord) -> None:
        self.text = text
        self.start_char = start_char
        self.end_char = end_char
        self.words = [word]


class _FakeSentence:
    def __init__(self, tokens: list[_FakeToken]) -> None:
        self.tokens = tokens


class _FakeDoc:
    def __init__(self, *, text: str, sentences: list[_FakeSentence]) -> None:
        self.text = text
        self.sentences = sentences


def test_stanza_doc_to_parsed_offsets_token_and_head_indices_across_sentences() -> None:
    doc = _FakeDoc(
        text="Alice sees Bob. Carol helps Dave.",
        sentences=[
            _FakeSentence(
                [
                    _FakeToken(
                        text="Alice",
                        start_char=0,
                        end_char=5,
                        word=_FakeWord(text="Alice", idx=1, head=2, upos="NOUN", deprel="nsubj"),
                    ),
                    _FakeToken(
                        text="sees",
                        start_char=6,
                        end_char=10,
                        word=_FakeWord(text="sees", idx=2, head=0, upos="VERB", deprel="root"),
                    ),
                    _FakeToken(
                        text="Bob",
                        start_char=11,
                        end_char=14,
                        word=_FakeWord(text="Bob", idx=3, head=2, upos="NOUN", deprel="obj"),
                    ),
                ]
            ),
            _FakeSentence(
                [
                    _FakeToken(
                        text="Carol",
                        start_char=16,
                        end_char=21,
                        word=_FakeWord(text="Carol", idx=1, head=2, upos="NOUN", deprel="nsubj"),
                    ),
                    _FakeToken(
                        text="helps",
                        start_char=22,
                        end_char=27,
                        word=_FakeWord(text="helps", idx=2, head=0, upos="VERB", deprel="root"),
                    ),
                    _FakeToken(
                        text="Dave",
                        start_char=28,
                        end_char=32,
                        word=_FakeWord(text="Dave", idx=3, head=2, upos="NOUN", deprel="obj"),
                    ),
                ]
            ),
        ],
    )

    parsed = _stanza_doc_to_parsed(doc)  # type: ignore[arg-type]

    assert [token.idx for token in parsed.tokens] == [0, 1, 2, 3, 4, 5]
    assert [token.head_idx for token in parsed.tokens] == [1, None, 1, 4, None, 4]


@pytest.mark.parametrize("language_tag", ["en", "es"])
def test_stanza_doc_to_parsed_offsets_indices_for_multisentence_fallback_languages(language_tag: str) -> None:
    doc = _FakeDoc(
        text="Alice sees Bob. Carol helps Dave.",
        sentences=[
            _FakeSentence(
                [
                    _FakeToken(
                        text="Alice",
                        start_char=0,
                        end_char=5,
                        word=_FakeWord(text="Alice", idx=1, head=2, upos="NOUN", deprel="nsubj"),
                    ),
                    _FakeToken(
                        text="sees",
                        start_char=6,
                        end_char=10,
                        word=_FakeWord(text="sees", idx=2, head=0, upos="VERB", deprel="root"),
                    ),
                    _FakeToken(
                        text="Bob",
                        start_char=11,
                        end_char=14,
                        word=_FakeWord(text="Bob", idx=3, head=2, upos="NOUN", deprel="obj"),
                    ),
                ]
            ),
            _FakeSentence(
                [
                    _FakeToken(
                        text="Carol",
                        start_char=16,
                        end_char=21,
                        word=_FakeWord(text="Carol", idx=1, head=2, upos="NOUN", deprel="nsubj"),
                    ),
                    _FakeToken(
                        text="helps",
                        start_char=22,
                        end_char=27,
                        word=_FakeWord(text="helps", idx=2, head=0, upos="VERB", deprel="root"),
                    ),
                    _FakeToken(
                        text="Dave",
                        start_char=28,
                        end_char=32,
                        word=_FakeWord(text="Dave", idx=3, head=2, upos="NOUN", deprel="obj"),
                    ),
                ]
            ),
        ],
    )

    parsed = _stanza_doc_to_parsed(doc, language_tag=language_tag)  # type: ignore[arg-type]

    assert parsed.language_tag == language_tag
    assert [token.idx for token in parsed.tokens] == [0, 1, 2, 3, 4, 5]
    assert [token.head_idx for token in parsed.tokens] == [1, None, 1, 4, None, 4]


def test_regex_pipeline_sets_language_tag_on_parsed_doc() -> None:
    pipeline = RegexNlpPipeline(language_tag="en")

    parsed = pipeline("Users must comply.")

    assert parsed.language_tag == "en"
