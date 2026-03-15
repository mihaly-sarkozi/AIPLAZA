from __future__ import annotations

import pytest

from apps.knowledge.application.sentence_splitter import split_sentences

pytestmark = pytest.mark.unit


def test_sentence_splitter_keeps_order():
    text = "Első mondat. Második mondat! Harmadik?"
    parts = split_sentences(text)
    assert parts == ["Első mondat.", "Második mondat!", "Harmadik?"]


def test_sentence_splitter_empty_input():
    assert split_sentences("   ") == []
