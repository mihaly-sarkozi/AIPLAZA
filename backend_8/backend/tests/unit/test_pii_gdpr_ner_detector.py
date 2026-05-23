from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.detectors.ner_detector import _normalize_person_span

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_normalize_person_span_trims_document_suffix() -> None:
    text = "János alacsony és kedvetlen, Feri Útlevélszáma PW897654"
    start = text.index("Feri")
    end = text.index("PW897654") - 1

    normalized = _normalize_person_span(text, start, end)

    assert normalized is not None
    norm_start, norm_end, matched = normalized
    assert matched == "Feri"
    assert text[norm_start:norm_end] == "Feri"


def test_normalize_person_span_keeps_regular_name() -> None:
    text = "Péter magas és kék szemű."
    start = text.index("Péter")
    end = start + len("Péter")

    normalized = _normalize_person_span(text, start, end)

    assert normalized == (start, end, "Péter")
