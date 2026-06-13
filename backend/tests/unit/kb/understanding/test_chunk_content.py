"""Chunking: limit, overlap, összevonás/bontás, sorrend és metaadat-megőrzés."""
from __future__ import annotations

import hashlib

import pytest

from apps.kb.kb_understanding.config.UnderstandingConf import UnderstandingConfig
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService

from tests.unit.kb.understanding.conftest import FakeChunkRepository, FakeContentRepository

pytestmark = pytest.mark.unit

_CONFIG = UnderstandingConfig(chunk_max_chars=200, chunk_min_chars=40, chunk_overlap_chars=30)


def _norm_part(text: str, *, order: int = 0, metadata=None, part_type: str = "TEXT"):
    return type(
        "NormPart",
        (),
        {
            "id": f"und_norm_part_{order}",
            "normalized_text": text,
            "page_number": 1,
            "part_index": order,
            "document_order": order,
            "part_type": part_type,
            "source_part_id": f"und_part_{order}",
            "metadata_json": dict(metadata or {}),
        },
    )()


def _normalized_summary():
    return NormalizedContentDto(
        normalized_content_id="und_norm_1",
        status="completed",
        part_count=1,
        total_chars=100,
        char_count=100,
    )


def _chunk(ctx, parts, chunk_repo=None):
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = list(parts)
    chunk_repo = chunk_repo or FakeChunkRepository()
    service = ChunkContentService(chunk_repo, content_repo, config=_CONFIG)
    result = service.run(ctx, _normalized_summary())
    return result.chunks, chunk_repo


def test_chunks_respect_max_char_limit(ctx):
    long_text = "Ez egy mondat, ami ismétlődik. " * 30
    chunks, _ = _chunk(ctx, [_norm_part(long_text.strip())])
    assert len(chunks) > 1
    assert all(len(chunk.text) <= _CONFIG.chunk_max_chars for chunk in chunks)


def test_long_split_has_split_metadata(ctx):
    words = " ".join(f"szo{index}" for index in range(120))
    chunks, _ = _chunk(ctx, [_norm_part(words)])
    assert len(chunks) >= 2
    assert chunks[0].metadata["split_index"] == 1
    assert chunks[0].metadata["split_count"] == len(chunks)
    assert chunks[0].metadata["parent_chunk_hash"]
    assert chunks[0].metadata["parent_chunk_id"]
    assert chunks[0].metadata["page_numbers_scope"] == "parent_logical_chunk"
    assert chunks[1].metadata["parent_chunk_hash"] == chunks[0].metadata["parent_chunk_hash"]


def test_table_always_own_chunk(ctx):
    paragraph = "Rövid bekezdés szöveg, elég hosszú chunkhoz. " * 2
    table_text = "| Név | Ár |\n| --- | --- |\n| Alma | 100 |"
    parts = [
        _norm_part(paragraph.strip(), order=0),
        _norm_part(
            table_text,
            order=1,
            part_type="TABLE",
            metadata={
                "block_kind": "table",
                "headers": ["Név", "Ár"],
                "rows": [["Alma", "100"]],
                "row_count": 1,
                "column_count": 2,
            },
        ),
        _norm_part(paragraph.strip(), order=2),
    ]
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = parts
    chunk_repo = FakeChunkRepository()
    result = ChunkContentService(chunk_repo, content_repo, config=_CONFIG).run(ctx, _normalized_summary())
    assert len(result.chunks) == 3
    assert result.chunks[1].chunk_type == ChunkType.TABLE
    assert result.chunks[1].metadata["table_refs"]
    assert result.chunks[1].metadata["headers"] == ["Név", "Ár"]
    assert result.trace_summary["table_chunks"] == 1


def test_uniform_metadata_required_fields(ctx):
    text = "Tartalom egy, kellően hosszú szöveg a chunkhoz. " * 2
    chunks, _ = _chunk(ctx, [_norm_part(text, order=0)])
    metadata = chunks[0].metadata
    for key in (
        "source_part_ids",
        "source_normalized_part_ids",
        "page_numbers",
        "document_orders",
        "heading_path",
        "heading_levels",
        "block_kinds",
    ):
        assert key in metadata


def test_long_split_has_overlap(ctx):
    words = " ".join(f"szo{index}" for index in range(120))
    chunks, _ = _chunk(ctx, [_norm_part(words)])
    assert len(chunks) >= 2
    first_tail = set(chunks[0].text.split()[-3:])
    assert first_tail & set(chunks[1].text.split())


def test_short_chunks_are_merged(ctx):
    parts = [
        _norm_part("Heading egy", order=0, metadata={"block_kind": "heading", "is_heading": True, "heading_level": 1}),
        _norm_part("Rövid.", order=1),
        _norm_part("Még egy rövid.", order=2),
    ]
    chunks, _ = _chunk(ctx, parts)
    assert len(chunks) == 1
    assert "Rövid." in chunks[0].text and "Még egy rövid." in chunks[0].text


def test_section_change_starts_new_chunk(ctx):
    filler_a = "A szekció tartalma, elég hosszú ahhoz hogy ne kelljen összevonni. " * 2
    filler_b = "B szekció tartalma, elég hosszú ahhoz hogy ne kelljen összevonni. " * 2
    parts = [
        _norm_part("A szekció", order=0, metadata={"block_kind": "heading", "is_heading": True, "heading_level": 1}),
        _norm_part(filler_a.strip(), order=1),
        _norm_part("B szekció", order=2, metadata={"block_kind": "heading", "is_heading": True, "heading_level": 1}),
        _norm_part(filler_b.strip(), order=3),
    ]
    chunks, _ = _chunk(ctx, parts)
    assert len(chunks) == 2
    assert chunks[0].section_title == "A szekció"
    assert chunks[1].section_title == "B szekció"


def test_order_metadata_checksum_and_tokens(ctx):
    text = "Tartalom egy, kellően hosszú szöveg a chunkhoz. " * 2
    part = _norm_part(text, order=0)
    part.page_number = 3
    chunks, repo = _chunk(ctx, [part])
    chunk = chunks[0]
    assert chunk.order_index == 0
    assert chunk.page_number == 3
    assert chunk.checksum == hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
    assert chunk.token_count >= 1
    persisted = repo.chunks[ctx.training_item_id]
    assert persisted[0].document_id == ctx.training_item_id
    assert persisted[0].source_id == ctx.raw_ref
    assert persisted[0].created_by == ctx.created_by


def test_chunk_type_follows_dominant_block(ctx):
    parts = [_norm_part("1. lépés: csináld ezt\n2. lépés: csináld azt", order=0)]
    chunks, _ = _chunk(ctx, parts)
    assert chunks[0].chunk_type == ChunkType.STEP


def test_version_increments_on_rerun(ctx):
    repo = FakeChunkRepository()
    parts = [_norm_part("Tartalom, ami elég hosszú a chunkoláshoz és nem kerül összevonásra.", order=0)]
    _chunk(ctx, parts, repo)
    _chunk(ctx, parts, repo)
    assert repo.chunks[ctx.training_item_id][0].version == 2


def test_no_parts_raises(ctx):
    content_repo = FakeContentRepository()
    chunk_repo = FakeChunkRepository()
    service = ChunkContentService(chunk_repo, content_repo, config=_CONFIG)
    with pytest.raises(UnderstandingValidationError) as excinfo:
        service.run(
            ctx,
            NormalizedContentDto(
                normalized_content_id="und_norm_1",
                status="completed",
                part_count=0,
                total_chars=0,
                char_count=0,
            ),
        )
    assert excinfo.value.code == UnderstandingErrorCode.CHUNKING_FAILED.value


def test_headers_are_skipped(ctx):
    parts = [
        _norm_part("Oldalszám", order=0, part_type="HEADER", metadata={"block_kind": "header"}),
        _norm_part("Valódi tartalom, elég hosszú ahhoz hogy chunk legyen belőle.", order=1),
    ]
    content_repo = FakeContentRepository()
    content_repo.normalized_parts[ctx.training_item_id] = parts
    chunk_repo = FakeChunkRepository()
    service = ChunkContentService(chunk_repo, content_repo, config=_CONFIG)
    result = service.run(ctx, _normalized_summary())
    assert result.trace_summary["headers_skipped"] == 1
    assert len(result.chunks) == 1
    assert "Valódi tartalom" in result.chunks[0].text
