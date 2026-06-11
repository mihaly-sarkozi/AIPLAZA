"""Chunking: limit, overlap, összevonás/bontás, sorrend és metaadat-megőrzés."""
from __future__ import annotations

import hashlib

import pytest

from apps.kb.kb_understanding.config.UnderstandingConf import UnderstandingConfig
from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService

from tests.unit.kb.understanding.conftest import FakeChunkRepository

pytestmark = pytest.mark.unit

_CONFIG = UnderstandingConfig(chunk_max_chars=200, chunk_min_chars=40, chunk_overlap_chars=30)


def _block(text: str, order: int, block_type=StructuredBlockType.PARAGRAPH, section=None, page=None):
    return StructuredBlockDto(
        block_type=block_type, text=text, order_index=order, page_number=page, section_title=section
    )


def _chunk(ctx, blocks, repo=None):
    repo = repo or FakeChunkRepository()
    service = ChunkContentService(repo, _CONFIG)
    return service.run(ctx, blocks), repo


def test_chunks_respect_max_char_limit(ctx):
    long_text = "Ez egy mondat, ami ismétlődik. " * 30
    chunks, _ = _chunk(ctx, [_block(long_text.strip(), 0)])
    assert len(chunks) > 1
    assert all(len(chunk.text) <= _CONFIG.chunk_max_chars for chunk in chunks)


def test_long_split_has_overlap(ctx):
    words = " ".join(f"szo{index}" for index in range(120))
    chunks, _ = _chunk(ctx, [_block(words, 0)])
    assert len(chunks) >= 2
    first_tail = set(chunks[0].text.split()[-3:])
    assert first_tail & set(chunks[1].text.split())


def test_short_chunks_are_merged(ctx):
    blocks = [
        _block("Heading egy", 0, StructuredBlockType.HEADING),
        _block("Rövid.", 1),
        _block("Még egy rövid.", 2),
    ]
    chunks, _ = _chunk(ctx, blocks)
    assert len(chunks) == 1
    assert "Rövid." in chunks[0].text and "Még egy rövid." in chunks[0].text


def test_section_change_starts_new_chunk(ctx):
    filler_a = "A szekció tartalma, elég hosszú ahhoz hogy ne kelljen összevonni. " * 2
    filler_b = "B szekció tartalma, elég hosszú ahhoz hogy ne kelljen összevonni. " * 2
    blocks = [
        _block("A szekció", 0, StructuredBlockType.HEADING),
        _block(filler_a.strip(), 1),
        _block("B szekció", 2, StructuredBlockType.HEADING),
        _block(filler_b.strip(), 3),
    ]
    chunks, _ = _chunk(ctx, blocks)
    assert len(chunks) == 2
    assert chunks[0].section_title == "A szekció"
    assert chunks[1].section_title == "B szekció"


def test_order_metadata_checksum_and_tokens(ctx):
    blocks = [_block("Tartalom egy, kellően hosszú szöveg a chunkhoz. " * 2, 0, page=3)]
    chunks, repo = _chunk(ctx, blocks)
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
    blocks = [
        _block("1. lépés: csináld ezt\n2. lépés: csináld azt", 0, StructuredBlockType.STEP),
    ]
    chunks, _ = _chunk(ctx, blocks)
    assert chunks[0].chunk_type == ChunkType.STEP


def test_version_increments_on_rerun(ctx):
    repo = FakeChunkRepository()
    blocks = [_block("Tartalom, ami elég hosszú a chunkoláshoz és nem kerül összevonásra.", 0)]
    _chunk(ctx, blocks, repo)
    _chunk(ctx, blocks, repo)
    assert repo.chunks[ctx.training_item_id][0].version == 2


def test_no_blocks_raises(ctx):
    with pytest.raises(UnderstandingValidationError) as excinfo:
        _chunk(ctx, [])
    assert excinfo.value.code == UnderstandingErrorCode.NO_CHUNKS.value
