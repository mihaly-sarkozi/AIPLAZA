"""Pipeline orchestráció: sorrend, hibaosztályozás, PARTIAL ág, trace-írás, események."""
from __future__ import annotations

from typing import Any

import pytest

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.service.ProcessingTraceService import ProcessingTraceService
from apps.kb.kb_understanding.service.UnderstandingPipelineService import (
    UnderstandingPipelineService,
)
from apps.kb.kb_understanding.validation.ValidateUnderstandingResult import UnderstandingChecklist

from tests.unit.kb.understanding.conftest import FakeJobRepository, FakeStepRunRepository

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
        status = (
            UnderstandingStatus.PARTIAL
            if had_optional_failures
            else UnderstandingStatus.READY_FOR_INDEXING
        )
        return status, UnderstandingChecklist()


def _build(recorder: _Recorder, *, failing: dict[str, Exception] | None = None):
    failing = failing or {}

    def step(name: str, result: Any = None) -> _Step:
        return _Step(recorder, name, result=result, error=failing.get(name))

    def emit(name: str):
        def _emit(**kwargs):
            recorder.events.append((name, kwargs))

        return _emit

    job_repo = FakeJobRepository()
    step_runs = FakeStepRunRepository()
    pipeline = UnderstandingPipelineService(
        job_repo,
        ProcessingTraceService(step_runs),
        extract_service=step("extract", ExtractedContentDto(text="t", char_count=1)),
        normalize_service=step("normalize", NormalizedContentDto(text="t", char_count=1)),
        structure_service=step("structure", ["block"]),
        chunk_service=step("chunk", ["chunk"]),
        entities_service=step("entities", []),
        enrich_service=step("enrich", []),
        embed_service=step("embed", 1),
        relationships_service=step("relationships", 0),
        score_service=step("score", []),
        validate_service=_ValidateStep(recorder, "validate", error=failing.get("validate")),
        emit_completed=emit("completed"),
        emit_failed=emit("failed"),
        emit_indexing_requested=emit("indexing"),
    )
    return pipeline, job_repo, step_runs, recorder


def test_happy_path_runs_steps_in_order_and_emits_indexing(ctx):
    recorder = _Recorder()
    pipeline, job_repo, step_runs, _ = _build(recorder)
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.READY_FOR_INDEXING
    assert recorder.order == [
        "extract",
        "normalize",
        "structure",
        "chunk",
        "entities",
        "enrich",
        "embed",
        "relationships",
        "score",
        "validate",
    ]
    assert job_repo.completed == (ctx.job_id, UnderstandingStatus.READY_FOR_INDEXING.value)
    assert [name for name, _ in recorder.events] == ["completed", "indexing"]
    # Minden lépésről készült trace.
    assert len(step_runs.runs) == 10
    assert all(result.status == "completed" for _, result in step_runs.runs)


def test_required_step_retryable_failure(ctx):
    recorder = _Recorder()
    error = UnderstandingProcessingError(UnderstandingErrorCode.STORAGE_ERROR, retryable=True)
    pipeline, job_repo, step_runs, _ = _build(recorder, failing={"extract": error})
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.RETRYABLE
    assert job_repo.failed["status"] == UnderstandingStatus.RETRYABLE.value
    assert job_repo.failed["error_code"] == UnderstandingErrorCode.STORAGE_ERROR.value
    assert job_repo.failed["retryable"] is True
    assert recorder.order == ["extract"]
    assert [name for name, _ in recorder.events] == ["failed"]
    assert step_runs.runs[0][1].status == "failed"


def test_required_step_content_failure_is_failed(ctx):
    recorder = _Recorder()
    error = UnderstandingProcessingError(UnderstandingErrorCode.EMPTY_CONTENT)
    pipeline, job_repo, _, _ = _build(recorder, failing={"normalize": error})
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.FAILED
    assert job_repo.failed["retryable"] is False


def test_optional_step_failure_results_in_partial(ctx):
    recorder = _Recorder()
    error = UnderstandingProcessingError(
        UnderstandingErrorCode.ENTITY_EXTRACTION_FAILED, retryable=True
    )
    pipeline, job_repo, step_runs, _ = _build(recorder, failing={"entities": error})
    status = pipeline.run(ctx)
    assert status == UnderstandingStatus.PARTIAL
    assert job_repo.completed == (ctx.job_id, UnderstandingStatus.PARTIAL.value)
    # A pipeline az opcionális hiba után is végigfut.
    assert "embed" in recorder.order and "validate" in recorder.order
    # PARTIAL esetén nincs indexing event.
    assert [name for name, _ in recorder.events] == ["completed"]
    failed_steps = [result.step.value for _, result in step_runs.runs if result.status == "failed"]
    assert failed_steps == ["entity_extraction"]


def test_status_history_follows_pipeline(ctx):
    recorder = _Recorder()
    pipeline, job_repo, _, _ = _build(recorder)
    pipeline.run(ctx)
    assert job_repo.status_history == [
        UnderstandingStatus.EXTRACTING.value,
        UnderstandingStatus.NORMALIZING.value,
        UnderstandingStatus.STRUCTURING.value,
        UnderstandingStatus.CHUNKING.value,
        UnderstandingStatus.EXTRACTING_ENTITIES.value,
        UnderstandingStatus.ENRICHING.value,
        UnderstandingStatus.EMBEDDING.value,
        UnderstandingStatus.BUILDING_RELATIONSHIPS.value,
        UnderstandingStatus.SCORING.value,
        UnderstandingStatus.VALIDATING.value,
    ]
