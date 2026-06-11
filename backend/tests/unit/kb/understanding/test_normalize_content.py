"""Normalize lépés: whitespace, oldalszám sorok, header/footer, duplikátumok, encoding."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.service.NormalizeContentService import NormalizeContentService

from tests.unit.kb.understanding.conftest import FakeContentRepository

pytestmark = pytest.mark.unit


def _normalize(ctx, text: str, page_map=None):
    repo = FakeContentRepository()
    service = NormalizeContentService(repo)
    result = service.run(
        ctx,
        ExtractedContentDto(text=text, page_map=page_map or [], char_count=len(text)),
    )
    return result, repo


def test_normalize_collapses_whitespace(ctx):
    result, _ = _normalize(ctx, "egy   két\t\thárom   \n\n\n\n\nnégy")
    assert result.text == "egy két három\n\nnégy"


def test_normalize_removes_page_number_lines(ctx):
    text = "Bekezdés egy\n12\n- 13 -\nPage 14\n15. oldal\nBekezdés kettő"
    result, _ = _normalize(ctx, text)
    assert "12" not in result.text
    assert "Page 14" not in result.text
    assert "Bekezdés egy" in result.text and "Bekezdés kettő" in result.text
    assert result.applied_rules["removed_page_number_lines"] == 4


def test_normalize_removes_repeated_header_footer(ctx):
    header = "ACME Kft. — Belső dokumentum"
    body = "\n".join(f"{header}\nTartalom {index} sora itt" for index in range(3))
    result, _ = _normalize(ctx, body)
    assert header not in result.text
    assert result.applied_rules["removed_header_footer_lines"] == 3


def test_normalize_dedupes_consecutive_lines(ctx):
    result, _ = _normalize(ctx, "ugyanaz a sor\nugyanaz a sor\nmásik sor")
    assert result.text.count("ugyanaz a sor") == 1
    assert result.applied_rules["deduplicated_lines"] == 1


def test_normalize_fixes_encoding_artifacts(ctx):
    result, _ = _normalize(ctx, "szó\u00a0köz\r\nmásodik\ufeff sor")
    assert "\u00a0" not in result.text
    assert "\r" not in result.text
    assert "\ufeff" not in result.text


def test_normalize_empty_output_raises(ctx):
    with pytest.raises(UnderstandingValidationError) as excinfo:
        _normalize(ctx, "   \n\n  ")
    assert excinfo.value.code == UnderstandingErrorCode.NORMALIZATION_FAILED.value


def test_normalize_persists_result(ctx):
    _, repo = _normalize(ctx, "valódi tartalom")
    assert repo.normalized[ctx.training_item_id].text == "valódi tartalom"
