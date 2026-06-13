"""Normalized part block classifier: metadata-first + heurisztika."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.chunk.NormalizedPartBlockClassifier import (
    LogicalBlockType,
    NormalizedPartBlockClassifier,
)
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType

pytestmark = pytest.mark.unit

_CLASSIFIER = NormalizedPartBlockClassifier()


def _classify(text: str, metadata=None, *, is_first=False):
    return _CLASSIFIER.classify(text=text, metadata=metadata or {}, is_first=is_first)


def test_classifies_title_heading_and_paragraph():
    text = "Felhasználói kézikönyv\n\n1. Bevezetés\n\nEz itt egy hosszabb bekezdés, amely leírja a rendszert."
    assert _classify("Felhasználói kézikönyv", is_first=True) == LogicalBlockType.TITLE
    assert _classify("1. Bevezetés") == LogicalBlockType.HEADING
    assert _classify("Ez itt egy hosszabb bekezdés, amely leírja a rendszert.") == LogicalBlockType.PARAGRAPH


def test_classifies_list_block():
    text = "- első elem\n- második elem\n• harmadik elem"
    assert _classify(text) == LogicalBlockType.LIST


def test_classifies_step_block():
    text = "1. Töltsd le a csomagot.\n2. Futtasd a telepítőt.\n3. Indítsd újra a gépet."
    assert _classify(text) == LogicalBlockType.STEP


def test_classifies_table_block():
    text = "Név | Ár | Készlet\nAlma | 100 | 5\nKörte | 200 | 3"
    assert _classify(text) == LogicalBlockType.TABLE


def test_classifies_faq_note_warning():
    faq = "K: Hogyan tudok jelszót módosítani?\nA profil oldalon."
    assert _classify(faq) == LogicalBlockType.FAQ
    assert _classify("Megjegyzés: a módosítás azonnal érvénybe lép.") == LogicalBlockType.NOTE
    assert _classify("Figyelem! A jelszó nem állítható vissza.") == LogicalBlockType.WARNING


def test_metadata_table_and_header():
    assert _classify("t", {"part_type": ExtractPartType.TABLE.value}) == LogicalBlockType.TABLE
    assert _classify("fejléc", {"part_type": ExtractPartType.HEADER.value}) == LogicalBlockType.HEADER
    assert _classify("lábléc", {"part_type": ExtractPartType.FOOTER.value}) == LogicalBlockType.FOOTER


def test_metadata_ocr_text():
    assert _classify(
        "OCR szöveg",
        {"part_type": ExtractPartType.OCR_TEXT.value, "block_kind": "ocr_text"},
    ) == LogicalBlockType.OCR_TEXT


def test_metadata_heading_from_docx():
    assert _classify(
        "1. Bevezetés",
        {"block_kind": "heading", "is_heading": True, "heading_level": 1},
    ) == LogicalBlockType.HEADING
