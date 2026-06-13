"""Extract metadata propagation through normalize and chunk."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService
from apps.kb.kb_understanding.service.NormalizeContentService import NormalizeContentService

from tests.unit.kb.understanding.conftest import FakeChunkRepository, FakeContentRepository

pytestmark = pytest.mark.unit


def _normalized_summary(*, part_count: int = 1, total_chars: int = 20) -> NormalizedContentDto:
    return NormalizedContentDto(
        normalized_content_id="und_norm_1",
        status="completed",
        part_count=part_count,
        total_chars=total_chars,
        char_count=total_chars,
    )


def test_normalize_preserves_part_metadata(ctx) -> None:
    repo = FakeContentRepository()
    repo.parts[ctx.training_item_id] = [
        type(
            "Part",
            (),
            {
                "id": "und_part_1",
                "text": "1. Bevezetés",
                "page_number": 1,
                "part_type": ExtractPartType.TEXT.value,
                "part_index": 0,
                "status": "completed",
                "metadata_json": {
                    "source": "docx_paragraph",
                    "block_kind": "heading",
                    "style_name": "Heading 1",
                    "heading_level": 1,
                    "document_order": 0,
                },
            },
        )()
    ]
    service = NormalizeContentService(repo)
    result = service.run(ctx, ExtractedContentDto.from_legacy(text="", page_map=[], char_count=0))

    assert result.part_count == 1
    part = repo.normalized_parts[ctx.training_item_id][0]
    assert part.metadata_json["block_kind"] == "heading"
    assert part.metadata_json["style_name"] == "Heading 1"
    assert part.source_part_id == "und_part_1"


def test_chunking_from_normalized_parts_carries_provenance(ctx) -> None:
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = [
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_part_1",
                "normalized_text": "1. Bevezetés",
                "page_number": 1,
                "part_index": 0,
                "document_order": 0,
                "part_type": ExtractPartType.TEXT.value,
                "source_part_id": "und_part_1",
                "metadata_json": {
                    "block_kind": "heading",
                    "is_heading": True,
                    "heading_level": 1,
                },
            },
        )(),
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_part_2",
                "normalized_text": "Tartalom, elég hosszú szöveg a chunkoláshoz.",
                "page_number": 1,
                "part_index": 1,
                "document_order": 1,
                "part_type": ExtractPartType.TEXT.value,
                "source_part_id": "und_part_2",
                "metadata_json": {"block_kind": "paragraph"},
            },
        )(),
    ]
    chunk_repo = FakeChunkRepository()
    result = ChunkContentService(chunk_repo, content_repo).run(ctx, _normalized_summary(part_count=2))

    assert result.trace_summary["input_parts"] == 2
    assert result.chunks[0].metadata["source_part_ids"] == ["und_part_1", "und_part_2"]
    assert result.chunks[0].metadata["source_normalized_part_ids"] == [
        "und_norm_part_1",
        "und_norm_part_2",
    ]


def test_chunking_marks_ocr_source(ctx) -> None:
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = [
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_part_ocr",
                "normalized_text": "OCR-ből kinyert szöveg, elég hosszú chunkhoz.",
                "page_number": 3,
                "part_index": 0,
                "document_order": 0,
                "part_type": ExtractPartType.OCR_TEXT.value,
                "source_part_id": "und_part_ocr",
                "metadata_json": {
                    "block_kind": "ocr_text",
                    "ocr_confidence": 0.91,
                    "ocr_language": "hun+eng+spa",
                },
            },
        )(),
    ]
    chunk_repo = FakeChunkRepository()
    result = ChunkContentService(chunk_repo, content_repo).run(ctx, _normalized_summary())

    assert result.trace_summary["ocr_chunks"] == 1
    assert result.chunks[0].metadata["is_from_ocr"] is True
    assert result.chunks[0].metadata["ocr_confidence"] == 0.91
    assert result.chunks[0].metadata["source_part_ids"] == ["und_part_ocr"]


def test_chunking_skips_headers_and_reports_trace(ctx) -> None:
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = [
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_header",
                "normalized_text": "Fejléc",
                "page_number": 1,
                "part_index": 0,
                "document_order": 0,
                "part_type": ExtractPartType.HEADER.value,
                "source_part_id": "und_part_h",
                "metadata_json": {"block_kind": "header"},
            },
        )(),
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_footer",
                "normalized_text": "Lábléc",
                "page_number": 1,
                "part_index": 1,
                "document_order": 1,
                "part_type": ExtractPartType.FOOTER.value,
                "source_part_id": "und_part_f",
                "metadata_json": {"block_kind": "footer"},
            },
        )(),
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_body",
                "normalized_text": "Törzs szöveg, elég hosszú ahhoz hogy chunk legyen.",
                "page_number": 1,
                "part_index": 2,
                "document_order": 2,
                "part_type": ExtractPartType.TEXT.value,
                "source_part_id": "und_part_b",
                "metadata_json": {"block_kind": "paragraph"},
            },
        )(),
    ]
    chunk_repo = FakeChunkRepository()
    result = ChunkContentService(chunk_repo, content_repo).run(ctx, _normalized_summary(part_count=3))

    assert result.trace_summary["headers_skipped"] == 1
    assert result.trace_summary["footers_skipped"] == 1
    assert len(result.chunks) == 1
    assert result.chunks[0].metadata["source_part_ids"] == ["und_part_b"]


def test_heading_path_tracker_builds_hierarchy() -> None:
    from apps.kb.kb_understanding.extract.heading_path import HeadingPathTracker

    tracker = HeadingPathTracker()
    tracker.update(1, "Ügyfélkezelés")
    second = tracker.update(2, "Onboarding")
    third = tracker.update(3, "CRM létrehozás")

    assert second["heading_path"] == ["Ügyfélkezelés", "Onboarding"]
    assert third["heading_path"] == ["Ügyfélkezelés", "Onboarding", "CRM létrehozás"]
    assert third["heading_levels"] == [1, 2, 3]


def test_normalize_preserves_pdf_guess_fields(ctx) -> None:
    repo = FakeContentRepository()
    repo.parts[ctx.training_item_id] = [
        type(
            "Part",
            (),
            {
                "id": "und_part_pdf",
                "text": "Fejléc szöveg",
                "page_number": 1,
                "part_type": ExtractPartType.TEXT.value,
                "part_index": 0,
                "status": "completed",
                "metadata_json": {
                    "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                    "font_names": ["Helvetica-Bold"],
                    "font_sizes": [16],
                    "dominant_font_size": 16,
                    "is_bold_guess": True,
                    "is_heading_guess": True,
                    "heading_confidence": 0.74,
                    "is_header_candidate": True,
                    "header_footer_confidence": 0.78,
                },
            },
        )()
    ]
    service = NormalizeContentService(repo)
    service.run(ctx, ExtractedContentDto.from_legacy(text="", page_map=[], char_count=0))

    entry = repo.normalized_parts[ctx.training_item_id][0].metadata_json
    assert entry["bbox"]["x0"] == 1
    assert entry["is_heading_guess"] is True
    assert entry["heading_confidence"] == 0.74
    assert entry["is_header_candidate"] is True
