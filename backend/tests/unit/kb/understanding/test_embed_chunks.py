"""Embedding lépés: fake embedder, modell-metaadat, dimenzió-validálás, hibák."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.service.EmbedChunksService import EmbedChunksService

from tests.unit.kb.understanding.conftest import FakeEmbeddingRepository

pytestmark = pytest.mark.unit


class _FakeEmbedder:
    def __init__(self, dimension: int = 4, broken: bool = False) -> None:
        self._dimension = dimension
        self._broken = broken
        self.calls: list[list[str]] = []

    @property
    def model_name(self) -> str:
        return "fake/model-v1"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._broken:
            return [[0.1] * (self._dimension + 1) for _ in texts]
        return [[0.1] * self._dimension for _ in texts]


def _chunk(chunk_id: str) -> KnowledgeChunkDto:
    return KnowledgeChunkDto(
        chunk_id=chunk_id,
        text=f"szöveg {chunk_id}",
        chunk_type=ChunkType.TEXT,
        order_index=0,
        token_count=3,
        checksum="abc",
    )


def test_embeds_chunks_and_summaries(ctx):
    repo = FakeEmbeddingRepository()
    embedder = _FakeEmbedder()
    service = EmbedChunksService(repo, embedder)
    chunks = [_chunk("chunk_1"), _chunk("chunk_2")]
    enrichments = [KnowledgeEnrichmentDto(chunk_id="chunk_1", summary="összefoglaló")]
    saved = service.run(ctx, chunks, enrichments)
    assert saved == 3  # 2 chunk_text + 1 summary
    targets = {(row.chunk_id, row.target) for row in repo.rows}
    assert ("chunk_1", "chunk_text") in targets
    assert ("chunk_1", "summary") in targets
    assert all(row.embedding_model == "fake/model-v1" for row in repo.rows)
    assert all(row.embedding_dimension == 4 for row in repo.rows)


def test_dimension_mismatch_fails_validation(ctx):
    service = EmbedChunksService(FakeEmbeddingRepository(), _FakeEmbedder(broken=True))
    with pytest.raises(UnderstandingValidationError) as excinfo:
        service.run(ctx, [_chunk("chunk_1")], [])
    assert excinfo.value.code == UnderstandingErrorCode.EMBEDDING_FAILED.value


def test_no_chunks_raises(ctx):
    service = EmbedChunksService(FakeEmbeddingRepository(), _FakeEmbedder())
    with pytest.raises(UnderstandingProcessingError) as excinfo:
        service.run(ctx, [], [])
    assert excinfo.value.code == UnderstandingErrorCode.NO_CHUNKS.value


@pytest.mark.slow
def test_local_embedder_real_model():
    pytest.importorskip("sentence_transformers")
    from apps.kb.kb_understanding.adapters.LocalEmbedder import LocalEmbedder

    embedder = LocalEmbedder()
    vectors = embedder.embed_texts(["teszt mondat"])
    assert len(vectors) == 1
    assert len(vectors[0]) == embedder.dimension
