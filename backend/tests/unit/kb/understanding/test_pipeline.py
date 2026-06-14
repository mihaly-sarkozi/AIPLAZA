"""Pipeline orchestráció: sorrend, hibaosztályozás, trace-írás, események."""
from __future__ import annotations

from typing import Any

import pytest

from apps.kb.kb_understanding.dto.ChunkContentResultDto import ChunkContentResultDto
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.service.UnderstandingPipelineService import (
    UnderstandingPipelineService,
)
from apps.kb.kb_understanding.validation.ValidateUnderstandingResult import UnderstandingChecklist

from tests.unit.kb.understanding.conftest import FakeFlowRecorder, FakeJobRepository

pytestmark = pytest.mark.unit


class _Recorder:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.events: list[tuple[str, dict]] = []


class _Step:
    def __init__(self, recorder: _Recorder, name: str, result: Any = None, error: Exception | None = None) -> None:
        self._recorder = recorder
        self._name = name
        self._result = result
        self._error = error

    def run(self, *args, **kwargs):
        self._recorder.order.append(self._name)
        if self._error is not None:
            raise self._error
        return self._result


class _ValidateStep(_Step):
    def run(self, ctx, *, had_optional_failures=False):
        self._recorder.order.append(self._name)
        if self._error is not None:
            raise self._error
        return UnderstandingStatus.READY_FOR_DISCOVERY, UnderstandingChecklist()


def _build(recorder: _Recorder, *, failing: dict[str, Exception] | None = None):
    failing = failing or {}

    def step(name: str, result: Any = None) -> _Step:
        return _Step(recorder, name, result=result, error=failing.get(name))

    def emit(name: str):
        def _emit(**kwargs):
            recorder.events.append((name, kwargs))

        return _emit

    job_repo = FakeJobRepository()
    flow_recorder = FakeFlowRecorder()
    pipeline = UnderstandingPipelineService(
        job_repo,
        extract_service=step("extract", ExtractedContentDto.from_legacy(text="t", char_count=1)),
        normalize_service=step(
            "normalize",
            NormalizedContentDto(normalized_content_id="und_norm_1", status="completed", char_count=1),
        ),
        chunk_service=step(
            "chunk",
            ChunkContentResultDto(chunks=[], trace_summary={"chunks_created": 1}),
        ),
        validate_service=_ValidateStep(recorder, "validate", error=failing.get("validate")),
        flow_recorder=flow_recorder,
        emit_discovery_requested=emit("discovery_requested"),
        emit_failed=emit("failed"),
    )
    return pipeline, job_repo, flow_recorder, recorder


def test_happy_path_runs_steps_in_order_and_emits_discovery_requested(ctx):
    recorder = _Recorder()
    pipeline, job_repo, flow_recorder, _ = _build(recorder)
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.READY_FOR_DISCOVERY
    assert recorder.order == ["extract", "normalize", "chunk", "validate"]
    assert job_repo.completed == (ctx.job_id, UnderstandingStatus.READY_FOR_DISCOVERY.value)
    assert [name for name, _ in recorder.events] == ["discovery_requested"]
    assert recorder.events[0][1]["understanding_job_id"] == ctx.job_id
    assert len(flow_recorder.completed) == 4


def test_required_step_retryable_failure(ctx):
    recorder = _Recorder()
    error = UnderstandingProcessingError(UnderstandingErrorCode.STORAGE_ERROR, retryable=True)
    pipeline, job_repo, flow_recorder, _ = _build(recorder, failing={"extract": error})
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.RETRYABLE
    assert job_repo.failed["retryable"] is True
    assert recorder.order == ["extract"]
    assert [name for name, _ in recorder.events] == ["failed"]
    assert len(flow_recorder.failed) == 1


def test_required_step_content_failure_is_failed(ctx):
    recorder = _Recorder()
    error = UnderstandingProcessingError(UnderstandingErrorCode.EMPTY_CONTENT)
    pipeline, job_repo, _, _ = _build(recorder, failing={"normalize": error})
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.FAILED
    assert job_repo.failed["retryable"] is False


def test_status_history_follows_pipeline(ctx):
    recorder = _Recorder()
    pipeline, job_repo, _, _ = _build(recorder)
    pipeline.run(ctx)
    assert job_repo.status_history == [
        UnderstandingStatus.EXTRACTING.value,
        UnderstandingStatus.NORMALIZING.value,
        UnderstandingStatus.CHUNKING.value,
        UnderstandingStatus.VALIDATING.value,
    ]
