"""Validate lépés: checklist és állapot-kimenetek (READY / PARTIAL / FAILED)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.service.ValidateUnderstandingService import (
    ValidateUnderstandingService,
)
from apps.kb.kb_understanding.validation.ValidateUnderstandingResult import (
    ValidateUnderstandingResult,
)

from tests.unit.kb.understanding.conftest import (
    FakeChunkRepository,
    FakeContentRepository,
    FakeEmbeddingRepository,
)

pytestmark = pytest.mark.unit


def _setup(ctx, *, chunks: int = 2, embeddings: int = 2, with_content: bool = True, with_source: bool = True):
    content_repo = FakeContentRepository()
    chunk_repo = FakeChunkRepository()
    embedding_repo = FakeEmbeddingRepository()
    if with_content:
        content_repo.extracted[ctx.training_item_id] = SimpleNamespace(char_count=100)
        content_repo.normalized[ctx.training_item_id] = SimpleNamespace(char_count=90)
    chunk_rows = [
        SimpleNamespace(id=f"chunk_{index}", source_id=ctx.raw_ref if with_source else "", version=1)
        for index in range(chunks)
    ]
    chunk_repo.chunks[ctx.training_item_id] = chunk_rows
    embedding_repo.rows = [
        SimpleNamespace(chunk_id=f"chunk_{index}") for index in range(embeddings)
    ]
    return ValidateUnderstandingService(content_repo, chunk_repo, embedding_repo)


def test_checklist_passes_when_everything_present():
    checklist = ValidateUnderstandingResult()(
        extracted_chars=10,
        normalized_chars=9,
        chunk_count=2,
        chunks_with_source=2,
        embedding_count=2,
    )
    assert checklist.core_complete
    assert checklist.missing == ()


def test_checklist_reports_missing_items():
    checklist = ValidateUnderstandingResult()(
        extracted_chars=0,
        normalized_chars=0,
        chunk_count=0,
        chunks_with_source=0,
        embedding_count=0,
    )
    assert not checklist.core_complete
    assert "extracted_text" in checklist.missing
    assert "chunks" in checklist.missing


def test_validate_ready_for_indexing(ctx):
    service = _setup(ctx)
    status, checklist = service.run(ctx)
    assert status == UnderstandingStatus.READY_FOR_INDEXING
    assert checklist.core_complete


def test_validate_partial_when_optional_failures(ctx):
    service = _setup(ctx)
    status, _ = service.run(ctx, had_optional_failures=True)
    assert status == UnderstandingStatus.PARTIAL


def test_validate_partial_when_embeddings_missing(ctx):
    service = _setup(ctx, embeddings=0)
    status, checklist = service.run(ctx)
    assert status == UnderstandingStatus.PARTIAL
    assert "embeddings" in checklist.missing


def test_validate_failed_when_no_chunks(ctx):
    service = _setup(ctx, chunks=0, embeddings=0)
    status, _ = service.run(ctx)
    assert status == UnderstandingStatus.FAILED
