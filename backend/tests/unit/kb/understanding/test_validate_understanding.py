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

from tests.unit.kb.understanding.conftest import FakeChunkRepository, FakeContentRepository

pytestmark = pytest.mark.unit


def _setup(ctx, *, chunks: int = 2, with_content: bool = True, with_source: bool = True):
    content_repo = FakeContentRepository()
    chunk_repo = FakeChunkRepository()
    if with_content:
        content_repo.extracted[ctx.training_item_id] = SimpleNamespace(char_count=100)
        content_repo.normalized[ctx.training_item_id] = SimpleNamespace(
            id="und_norm_1",
            part_count=1,
            total_chars=90,
        )
        content_repo.parts[ctx.training_item_id] = [SimpleNamespace(part_type="TEXT", text="x")]
        content_repo.normalized_parts[ctx.training_item_id] = [
            SimpleNamespace(status="completed", normalized_text="x")
        ]
    chunk_rows = [
        SimpleNamespace(id=f"chunk_{index}", source_id=ctx.raw_ref if with_source else "", version=1)
        for index in range(chunks)
    ]
    chunk_repo.chunks[ctx.training_item_id] = chunk_rows
    return ValidateUnderstandingService(content_repo, chunk_repo)


def test_checklist_passes_when_everything_present():
    checklist = ValidateUnderstandingResult()(
        has_extracted_content=True,
        usable_part_count=1,
        has_normalized_summary=True,
        normalized_part_count=1,
        chunk_count=2,
        chunks_with_source=2,
    )
    assert checklist.core_complete
    assert checklist.missing == ()


def test_checklist_reports_missing_items():
    checklist = ValidateUnderstandingResult()(
        has_extracted_content=False,
        usable_part_count=0,
        has_normalized_summary=False,
        normalized_part_count=0,
        chunk_count=0,
        chunks_with_source=0,
    )
    assert not checklist.core_complete
    assert "extracted_content" in checklist.missing
    assert "usable_parts" in checklist.missing
    assert "normalized_parts" in checklist.missing
    assert "chunks" in checklist.missing


def test_validate_ready_for_discovery(ctx):
    service = _setup(ctx)
    status, checklist = service.run(ctx)
    assert status == UnderstandingStatus.READY_FOR_DISCOVERY
    assert checklist.core_complete


def test_validate_partial_when_chunks_without_full_content(ctx):
    service = _setup(ctx, with_content=False, chunks=1, with_source=True)
    status, _ = service.run(ctx)
    assert status == UnderstandingStatus.PARTIAL


def test_validate_failed_when_no_chunks(ctx):
    service = _setup(ctx, chunks=0)
    status, _ = service.run(ctx)
    assert status == UnderstandingStatus.FAILED
