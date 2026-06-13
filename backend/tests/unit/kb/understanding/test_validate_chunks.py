"""Chunk validáció: kemény hibák vs. figyelmeztetések."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.validation.ValidateChunks import ValidateChunks

pytestmark = pytest.mark.unit


def _chunk(**metadata) -> KnowledgeChunkDto:
    return KnowledgeChunkDto(
        chunk_id="chunk_1",
        text="Tartalom",
        chunk_type=ChunkType.TEXT,
        order_index=0,
        token_count=1,
        checksum="abc",
        metadata=metadata,
    )


def test_validate_chunks_warns_on_missing_source_part_ids() -> None:
    result = ValidateChunks()([_chunk(heading_path=[])])
    assert "missing source_part_ids" in result.warnings[0]


def test_validate_chunks_warns_on_table_without_refs() -> None:
    result = ValidateChunks()(
        [
            KnowledgeChunkDto(
                chunk_id="chunk_1",
                text="Tartalom",
                chunk_type=ChunkType.TABLE,
                order_index=0,
                token_count=1,
                checksum="abc",
                metadata={"heading_path": [], "source_part_ids": ["und_part_1"]},
            )
        ]
    )
    assert any("TABLE chunk missing table_refs" in warning for warning in result.warnings)


def test_validate_chunks_raises_on_empty_list() -> None:
    with pytest.raises(UnderstandingValidationError) as excinfo:
        ValidateChunks()([])
    assert excinfo.value.code == UnderstandingErrorCode.NO_CHUNKS.value
