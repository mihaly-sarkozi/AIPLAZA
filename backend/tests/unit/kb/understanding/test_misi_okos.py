from __future__ import annotations

import pytest

from apps.kb.kb_understanding.adapters.ManualTextExtractorAdapter import ManualTextExtractorAdapter
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService
from apps.kb.kb_understanding.service.ExtractContentService import ExtractContentService
from apps.kb.kb_understanding.service.NormalizeContentService import NormalizeContentService
from apps.kb.kb_understanding.service.UnderstandingPipelineService import UnderstandingPipelineService
from apps.kb.kb_understanding.service.ValidateUnderstandingService import ValidateUnderstandingService

from tests.unit.kb.understanding.conftest import (
    FakeChunkRepository,
    FakeContentRepository,
    FakeFlowRecorder,
    FakeJobRepository,
)

pytestmark = pytest.mark.unit


class _FakeStorage:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read_bytes(self, *, raw_ref: str) -> bytes:
        return self._payload

    def stat_bytes(self, *, raw_ref: str) -> int:
        return len(self._payload)


def test_misi_okos_understanding_pipeline_creates_artifacts_and_emits_discovery(ctx):
    events: list[str] = []
    content_repo = FakeContentRepository()
    chunk_repo = FakeChunkRepository()
    job_repo = FakeJobRepository()
    flow_recorder = FakeFlowRecorder()

    def emit_discovery_requested(**kwargs):
        events.append("discovery_requested")

    pipeline = UnderstandingPipelineService(
        job_repo,
        extract_service=ExtractContentService(
            content_repo,
            _FakeStorage(b"Misi okos"),
            pdf_extractor=ManualTextExtractorAdapter(),
            docx_extractor=ManualTextExtractorAdapter(),
            text_extractor=ManualTextExtractorAdapter(),
        ),
        normalize_service=NormalizeContentService(content_repo),
        chunk_service=ChunkContentService(chunk_repo, content_repo),
        validate_service=ValidateUnderstandingService(content_repo, chunk_repo),
        flow_recorder=flow_recorder,
        emit_discovery_requested=emit_discovery_requested,
    )

    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.READY_FOR_DISCOVERY
    assert ctx.training_item_id in content_repo.extracted
    assert ctx.training_item_id in content_repo.normalized
    assert len(content_repo.normalized_parts.get(ctx.training_item_id, [])) >= 1
    assert len(chunk_repo.chunks.get(ctx.training_item_id, [])) >= 1
    assert events == ["discovery_requested"]
