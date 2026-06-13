"""Extract metadata propagation through normalize, structure, chunk."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService
from apps.kb.kb_understanding.service.DetectStructureService import DetectStructureService
from apps.kb.kb_understanding.service.NormalizeContentService import NormalizeContentService

from tests.unit.kb.understanding.conftest import FakeChunkRepository, FakeContentRepository, FakeStructureRepository

pytestmark = pytest.mark.unit


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


def test_detect_structure_uses_normalized_parts(ctx) -> None:
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
                "normalized_text": "Tartalom",
                "page_number": 1,
                "part_index": 1,
                "document_order": 1,
                "part_type": ExtractPartType.TEXT.value,
                "source_part_id": "und_part_2",
                "metadata_json": {"block_kind": "paragraph"},
            },
        )(),
    ]
    structure_repo = FakeStructureRepository()
    service = DetectStructureService(structure_repo, content_repo)
    normalized = NormalizedContentDto(
        normalized_content_id="und_norm_1",
        status="completed",
        part_count=2,
        total_chars=20,
        char_count=20,
    )
    blocks = service.run(ctx, normalized)

    assert blocks[0].block_type == StructuredBlockType.HEADING
    assert blocks[1].block_type == StructuredBlockType.PARAGRAPH
    assert blocks[0].metadata["block_kind"] == "heading"
    assert blocks[0].source_normalized_part_id == "und_norm_part_1"
    assert blocks[0].source_part_id == "und_part_1"
    stored = structure_repo.blocks[ctx.training_item_id][0]
    assert stored.source_normalized_part_id == "und_norm_part_1"
    assert stored.source_part_id == "und_part_1"


def test_detect_structure_marks_ocr_source_in_metadata(ctx) -> None:
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = [
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_part_ocr",
                "normalized_text": "OCR-ből kinyert szöveg",
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
    structure_repo = FakeStructureRepository()
    service = DetectStructureService(structure_repo, content_repo)
    blocks = service.run(
        ctx,
        NormalizedContentDto(
            normalized_content_id="und_norm_1",
            status="completed",
            part_count=1,
            total_chars=24,
            char_count=24,
        ),
    )

    assert blocks[0].metadata["is_from_ocr"] is True
    assert blocks[0].is_from_ocr is True
    assert blocks[0].source_normalized_part_id == "und_norm_part_ocr"
    assert blocks[0].source_part_id == "und_part_ocr"
    assert blocks[0].metadata["part_type"] == ExtractPartType.OCR_TEXT.value
    assert blocks[0].metadata["ocr_confidence"] == 0.91
    assert blocks[0].metadata["block_kind"] == "ocr_text"
    stored = structure_repo.blocks[ctx.training_item_id][0]
    assert stored.is_from_ocr is True
    assert stored.source_part_id == "und_part_ocr"


def test_detect_structure_ocr_heading_not_forced_to_paragraph(ctx) -> None:
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = [
        type(
            "NormPart",
            (),
            {
                "id": "und_norm_part_ocr_h",
                "normalized_text": "1. Bevezetés",
                "page_number": 1,
                "part_index": 0,
                "document_order": 0,
                "part_type": ExtractPartType.OCR_TEXT.value,
                "source_part_id": "und_part_ocr_h",
                "metadata_json": {
                    "block_kind": "ocr_text",
                    "is_heading": True,
                    "heading_level": 1,
                    "is_from_ocr": True,
                },
            },
        )(),
    ]
    structure_repo = FakeStructureRepository()
    service = DetectStructureService(structure_repo, content_repo)
    blocks = service.run(
        ctx,
        NormalizedContentDto(
            normalized_content_id="und_norm_1",
            status="completed",
            part_count=1,
            total_chars=12,
            char_count=12,
        ),
    )

    assert blocks[0].block_type == StructuredBlockType.HEADING
    assert blocks[0].metadata["is_from_ocr"] is True
    assert blocks[0].is_from_ocr is True


def test_chunk_carries_source_metadata(ctx) -> None:
    repo = FakeChunkRepository()
    service = ChunkContentService(repo)
    blocks = [
        StructuredBlockDto(
            block_type=StructuredBlockType.HEADING,
            text="Fejezet",
            order_index=0,
            page_number=2,
            metadata={"source_part_id": "und_part_9", "block_kind": "heading", "heading_path": ["Fejezet"]},
        ),
        StructuredBlockDto(
            block_type=StructuredBlockType.PARAGRAPH,
            text="Részletes tartalom",
            order_index=1,
            page_number=2,
            section_title="Fejezet",
            metadata={"source_part_id": "und_part_10", "block_kind": "paragraph", "heading_path": ["Fejezet"]},
        ),
    ]
    chunks = service.run(ctx, blocks)

    assert chunks[0].metadata["source_part_ids"] == ["und_part_9", "und_part_10"]
    assert chunks[0].metadata["heading_path"] == ["Fejezet"]
    assert chunks[0].metadata["block_kinds"] == ["heading", "paragraph"]


def test_chunk_marks_ocr_from_block_column(ctx) -> None:
    repo = FakeChunkRepository()
    service = ChunkContentService(repo)
    blocks = [
        StructuredBlockDto(
            block_type=StructuredBlockType.PARAGRAPH,
            text="OCR szöveg",
            order_index=0,
            page_number=4,
            is_from_ocr=True,
            metadata={"source_part_id": "und_part_ocr", "ocr_confidence": 0.88},
        ),
    ]
    chunks = service.run(ctx, blocks)

    assert chunks[0].metadata["is_from_ocr"] is True
    assert chunks[0].metadata["ocr_confidence"] == 0.88


def test_chunk_marks_ocr_from_block_metadata(ctx) -> None:
    repo = FakeChunkRepository()
    service = ChunkContentService(repo)
    blocks = [
        StructuredBlockDto(
            block_type=StructuredBlockType.PARAGRAPH,
            text="OCR szöveg",
            order_index=0,
            page_number=4,
            metadata={
                "source_part_id": "und_part_ocr",
                "block_kind": "ocr_text",
                "part_type": ExtractPartType.OCR_TEXT.value,
                "is_from_ocr": True,
                "ocr_confidence": 0.88,
            },
        ),
    ]
    chunks = service.run(ctx, blocks)

    assert chunks[0].metadata["is_from_ocr"] is True
    assert chunks[0].metadata["ocr_confidence"] == 0.88


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
