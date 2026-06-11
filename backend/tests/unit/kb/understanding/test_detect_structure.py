"""Structure detection: blokk-klasszifikáció és section követés."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType
from apps.kb.kb_understanding.service.DetectStructureService import DetectStructureService

from tests.unit.kb.understanding.conftest import FakeStructureRepository

pytestmark = pytest.mark.unit


def _detect(ctx, text: str, page_map=None):
    repo = FakeStructureRepository()
    service = DetectStructureService(repo)
    blocks = service.run(
        ctx, NormalizedContentDto(text=text, page_map=page_map or [], char_count=len(text))
    )
    return blocks, repo


def test_detects_title_heading_and_paragraph(ctx):
    text = "Felhasználói kézikönyv\n\n1. Bevezetés\n\nEz itt egy hosszabb bekezdés, amely leírja a rendszert."
    blocks, _ = _detect(ctx, text)
    assert [block.block_type for block in blocks] == [
        StructuredBlockType.TITLE,
        StructuredBlockType.HEADING,
        StructuredBlockType.PARAGRAPH,
    ]
    assert blocks[2].section_title == "1. Bevezetés"


def test_detects_list_block(ctx):
    text = "Cím sor\n\n- első elem\n- második elem\n• harmadik elem"
    blocks, _ = _detect(ctx, text)
    assert blocks[1].block_type == StructuredBlockType.LIST


def test_detects_step_block(ctx):
    text = "Telepítés\n\n1. Töltsd le a csomagot.\n2. Futtasd a telepítőt.\n3. Indítsd újra a gépet."
    blocks, _ = _detect(ctx, text)
    assert blocks[1].block_type == StructuredBlockType.STEP


def test_detects_table_block(ctx):
    text = "Árlista\n\nNév | Ár | Készlet\nAlma | 100 | 5\nKörte | 200 | 3"
    blocks, _ = _detect(ctx, text)
    assert blocks[1].block_type == StructuredBlockType.TABLE


def test_detects_faq_note_warning(ctx):
    text = (
        "Gyakori kérdések\n\n"
        "K: Hogyan tudok jelszót módosítani?\nA profil oldalon.\n\n"
        "Megjegyzés: a módosítás azonnal érvénybe lép.\n\n"
        "Figyelem! A jelszó nem állítható vissza."
    )
    blocks, _ = _detect(ctx, text)
    types = [block.block_type for block in blocks]
    assert StructuredBlockType.FAQ in types
    assert StructuredBlockType.NOTE in types
    assert StructuredBlockType.WARNING in types


def test_order_index_is_sequential_and_persisted(ctx):
    text = "Cím\n\nElső bekezdés tartalma.\n\nMásodik bekezdés tartalma."
    blocks, repo = _detect(ctx, text)
    assert [block.order_index for block in blocks] == [0, 1, 2]
    assert len(repo.blocks[ctx.training_item_id]) == 3


def test_page_number_resolved_from_page_map(ctx):
    text = "Első oldal szövege itt található.\n\nMásodik oldal szövege itt található."
    page_map = [
        {"page": 1, "start": 0, "end": 32},
        {"page": 2, "start": 32, "end": len(text)},
    ]
    blocks, _ = _detect(ctx, text, page_map=page_map)
    assert blocks[0].page_number == 1
    assert blocks[1].page_number == 2
