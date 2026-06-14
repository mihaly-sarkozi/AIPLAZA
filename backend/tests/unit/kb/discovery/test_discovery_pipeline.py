from __future__ import annotations

from typing import Any

import pytest

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.service.DiscoveryPipelineService import DiscoveryPipelineService
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import RelationshipBuildResult
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import LocalKnowledgeEnrichmentResult
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.validation.ValidateDiscoveryResult import DiscoveryChecklist
from tests.unit.kb.understanding.conftest import FakeFlowRecorder

pytestmark = pytest.mark.unit


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []


class _Step:
    def __init__(self, name: str, result: Any = None, error: Exception | None = None) -> None:
        self._name = name
        self._result = result
        self._error = error

    def run(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeJobRepo:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.completed = None

    def set_status(self, job_id, status):
        self.statuses.append(status.value)

    def mark_completed(self, job_id, status):
        self.completed = status

    def mark_failed(self, *args, **kwargs):
        pass


def _ctx():
    return DiscoveryJobContext(
        job_id="disc_job_1",
        understanding_job_id="und_job_1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id="kb1",
        tenant_slug="tenant",
        created_by=1,
        source_type="text",
        title="t",
    )


def _chunks():
    return [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Az ACME Kft. 2026. július 1-től a budapesti irodában HubSpotot használ.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]


def test_discovery_pipeline_happy_path():
    recorder = _Recorder()

    def emit(name: str):
        def _emit(**kwargs):
            recorder.events.append((name, kwargs))

        return _emit

    from apps.kb.kb_discovery.dto.LanguageDetectionResult import LanguageDetectionResult

    from apps.kb.kb_discovery.dto.DiscoveryResultDtos import (
        ProcessExtractionResult,
        SpatialExtractionResult,
        TemporalExtractionResult,
    )

    pipeline = DiscoveryPipelineService(
        _FakeJobRepo(),
        language_service=_Step(
            "language",
            LanguageDetectionResult(language_code="hu", language_confidence=0.8, chunk_languages={"c1": "hu"}),
        ),
        entity_service=_Step("entity", ([], [])),
        enrichment_service=_Step(
            "enrichment",
            LocalKnowledgeEnrichmentResult(
                enrichments=(
                    KnowledgeEnrichmentDto(
                        chunk_id="c1",
                        metadata={"keyword_count": 1, "topic_count": 1, "top_topics": ["sales"]},
                    ),
                ),
                trace={"enrichments_created": 1},
            ),
        ),
        temporal_service=_Step("temporal", TemporalExtractionResult(trace={"temporal_mentions_created": 1})),
        spatial_service=_Step("spatial", SpatialExtractionResult(trace={"spatial_mentions_created": 1})),
        process_service=_Step("process", ProcessExtractionResult(trace={"process_mentions_created": 0})),
        relationship_service=_Step("relationship", RelationshipBuildResult(relationship_count=2)),
        scoring_service=_Step("score", []),
        validate_service=_Step(
            "validate",
            (DiscoveryStatus.READY_FOR_EMBEDDING, DiscoveryChecklist(has_chunks=True, has_enrichments=True, has_scores=True)),
        ),
        flow_recorder=FakeFlowRecorder(),
        emit_completed=emit("completed"),
        emit_failed=emit("failed"),
        emit_embedding_requested=emit("embedding"),
    )
    status = pipeline.run(_ctx(), _chunks())
    assert status == DiscoveryStatus.READY_FOR_EMBEDDING
    assert [name for name, _ in recorder.events] == ["completed", "embedding"]


def test_discovery_pipeline_partial_on_optional_failure():
    recorder = _Recorder()

    def emit(name: str):
        def _emit(**kwargs):
            recorder.events.append((name, kwargs))

        return _emit

    from apps.kb.kb_discovery.dto.DiscoveryResultDtos import (
        ProcessExtractionResult,
        RelationshipBuildResult,
        SpatialExtractionResult,
        TemporalExtractionResult,
    )

    pipeline = DiscoveryPipelineService(
        _FakeJobRepo(),
        language_service=_Step("language", error=RuntimeError("language fail")),
        entity_service=_Step("entity", ([], [])),
        enrichment_service=_Step(
            "enrichment",
            LocalKnowledgeEnrichmentResult(
                enrichments=(KnowledgeEnrichmentDto(chunk_id="c1", metadata={"keyword_count": 0}),),
            ),
        ),
        temporal_service=_Step("temporal", TemporalExtractionResult()),
        spatial_service=_Step("spatial", SpatialExtractionResult()),
        process_service=_Step("process", ProcessExtractionResult()),
        relationship_service=_Step("relationship", RelationshipBuildResult(relationship_count=0)),
        scoring_service=_Step("score", []),
        validate_service=_Step(
            "validate",
            (DiscoveryStatus.PARTIAL, DiscoveryChecklist(has_chunks=True)),
        ),
        flow_recorder=FakeFlowRecorder(),
        emit_completed=emit("completed"),
        emit_failed=emit("failed"),
        emit_embedding_requested=emit("embedding"),
    )
    status = pipeline.run(_ctx(), _chunks())
    assert status == DiscoveryStatus.PARTIAL
