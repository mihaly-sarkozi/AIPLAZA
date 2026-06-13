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

    assert len(result.part_map) == 1
    assert result.part_map[0]["block_kind"] == "heading"
    assert result.part_map[0]["style_name"] == "Heading 1"
    assert result.part_map[0]["source_part_id"] == "und_part_1"


def test_detect_structure_uses_extract_metadata(ctx) -> None:
    repo = FakeStructureRepository()
    service = DetectStructureService(repo)
    normalized = NormalizedContentDto(
        text="1. Bevezetés\n\nTartalom",
        part_map=[
            {
                "start": 0,
                "end": 13,
                "page": 1,
                "part_type": ExtractPartType.TEXT.value,
                "block_kind": "heading",
                "is_heading": True,
                "heading_level": 1,
            },
                {
                    "start": 14,
                    "end": 22,
                    "page": 1,
                    "part_type": ExtractPartType.TEXT.value,
                    "block_kind": "paragraph",
                },
            ],
            char_count=22,
    )
    blocks = service.run(ctx, normalized)

    assert blocks[0].block_type == StructuredBlockType.HEADING
    assert blocks[1].block_type == StructuredBlockType.PARAGRAPH
    assert blocks[0].metadata["block_kind"] == "heading"


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
    result = service.run(ctx, ExtractedContentDto.from_legacy(text="", page_map=[], char_count=0))

    entry = result.part_map[0]
    assert entry["bbox"]["x0"] == 1
    assert entry["is_heading_guess"] is True
    assert entry["heading_confidence"] == 0.74
    assert entry["is_header_candidate"] is True
