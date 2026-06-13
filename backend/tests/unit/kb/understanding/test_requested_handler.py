"""UNDERSTANDING_REQUESTED handler: idempotencia és hibatűrés."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.events.understanding_requested_handler import (
    make_understanding_requested_handler,
)

pytestmark = pytest.mark.unit

_PAYLOAD = {
    "tenant_slug": "tenant1",
    "training_batch_id": "batch_1",
    "training_item_id": "item_1",
    "knowledge_base_id": "kb-uuid-1",
    "created_by": 1,
}


class _FakeStart:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict] = []

    def start(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(job_id="und_job_1", training_item_id=kwargs["training_item_id"])


class _FakePipeline:
    def __init__(self) -> None:
        self.calls: list = []

    def run(self, ctx):
        self.calls.append(ctx)
        return UnderstandingStatus.READY_FOR_DISCOVERY


def _handler(start_error: Exception | None = None):
    start = _FakeStart(start_error)
    pipeline = _FakePipeline()
    services = SimpleNamespace(start_service=start, pipeline=pipeline)
    return make_understanding_requested_handler(lambda: services), start, pipeline


def test_handler_runs_start_and_pipeline():
    handler, start, pipeline = _handler()
    handler(dict(_PAYLOAD))
    assert len(start.calls) == 1
    assert start.calls[0]["training_item_id"] == "item_1"
    assert len(pipeline.calls) == 1


def test_handler_ignores_invalid_payload():
    handler, start, pipeline = _handler()
    handler({"training_item_id": "", "training_batch_id": "b", "knowledge_base_id": "kb"})
    assert start.calls == []
    assert pipeline.calls == []


def test_handler_is_idempotent_when_job_already_running():
    error = UnderstandingProcessingError(UnderstandingErrorCode.JOB_ALREADY_RUNNING)
    handler, _, pipeline = _handler(start_error=error)
    # Nem dob kivételt → az outbox nem próbálkozik újra feleslegesen.
    handler(dict(_PAYLOAD))
    assert pipeline.calls == []


def test_handler_swallows_missing_item():
    error = UnderstandingNotFoundError(UnderstandingErrorCode.ITEM_NOT_FOUND)
    handler, _, pipeline = _handler(start_error=error)
    handler(dict(_PAYLOAD))
    assert pipeline.calls == []


def test_handler_propagates_unexpected_errors():
    error = UnderstandingProcessingError(UnderstandingErrorCode.RAW_REF_MISSING)
    handler, _, _ = _handler(start_error=error)
    with pytest.raises(UnderstandingProcessingError):
        handler(dict(_PAYLOAD))
