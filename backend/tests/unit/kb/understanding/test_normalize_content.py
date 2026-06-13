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
    repo.parts[ctx.training_item_id] = [
        type(
            "Part",
            (),
            {
                "id": "und_part_1",
                "text": text,
                "page_number": 1,
                "part_type": "TEXT",
                "part_index": 0,
                "status": "completed",
                "metadata_json": {},
            },
        )()
    ]
    service = NormalizeContentService(repo)
    result = service.run(
        ctx,
        ExtractedContentDto.from_legacy(text=text, page_map=page_map or [], char_count=len(text)),
    )
    return result, repo


def test_normalize_collapses_whitespace(ctx):
    result, repo = _normalize(ctx, "egy   két\t\thárom   \n\n\n\n\nnégy")
    assert repo.normalized_parts[ctx.training_item_id][0].normalized_text == "egy két három\n\nnégy"


def test_normalize_removes_page_number_lines(ctx):
    text = "Bekezdés egy\n12\n- 13 -\nPage 14\n15. oldal\nBekezdés kettő"
    result, repo = _normalize(ctx, text)
    normalized = repo.normalized_parts[ctx.training_item_id][0].normalized_text
    assert "12" not in normalized
    assert "Page 14" not in normalized
    assert "Bekezdés egy" in normalized and "Bekezdés kettő" in normalized
    assert result.applied_rules["removed_page_number_lines"] == 4


def test_normalize_removes_repeated_header_footer(ctx):
    header = "ACME Kft. — Belső dokumentum"
    body = "\n".join(f"{header}\nTartalom {index} sora itt" for index in range(3))
    result, repo = _normalize(ctx, body)
    normalized = repo.normalized_parts[ctx.training_item_id][0].normalized_text
    assert header not in normalized
    assert result.applied_rules["removed_header_footer_lines"] == 3


def test_normalize_dedupes_consecutive_lines(ctx):
    result, repo = _normalize(ctx, "ugyanaz a sor\nugyanaz a sor\nmásik sor")
    normalized = repo.normalized_parts[ctx.training_item_id][0].normalized_text
    assert normalized.count("ugyanaz a sor") == 1
    assert result.applied_rules["deduplicated_lines"] == 1


def test_normalize_fixes_encoding_artifacts(ctx):
    result, repo = _normalize(ctx, "szó\u00a0köz\r\nmásodik\ufeff sor")
    normalized = repo.normalized_parts[ctx.training_item_id][0].normalized_text
    assert "\u00a0" not in normalized
    assert "\r" not in normalized
    assert "\ufeff" not in normalized


def test_normalize_empty_output_raises(ctx):
    with pytest.raises(UnderstandingValidationError) as excinfo:
        _normalize(ctx, "   \n\n  ")
    assert excinfo.value.code == UnderstandingErrorCode.NORMALIZATION_FAILED.value


def test_normalize_persists_summary_and_parts(ctx):
    _, repo = _normalize(ctx, "valódi tartalom")
    assert repo.normalized[ctx.training_item_id].part_count == 1
    assert repo.normalized_parts[ctx.training_item_id][0].normalized_text == "valódi tartalom"
    assert repo.normalized_parts[ctx.training_item_id][0].source_part_id == "und_part_1"


def test_normalize_trace_summary(ctx):
    result, _ = _normalize(ctx, "valódi tartalom")
    assert result.trace_summary["normalized_parts"] == 1
    assert result.trace_summary["input_parts"] == 1
    assert result.trace_summary["status"] == "COMPLETED"
