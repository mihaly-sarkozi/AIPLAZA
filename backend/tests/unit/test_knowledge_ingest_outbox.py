from __future__ import annotations

import pytest

from apps.knowledge import events as knowledge_events
from apps.knowledge.api import background_jobs as knowledge_background_jobs

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_knowledge_ingest_pipeline_handler_invokes_sync_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | None, str, int | None]] = []

    def _fake_runner(*, tenant_slug: str | None, run_id: str, created_by: int | None, facade=None) -> None:
        calls.append((tenant_slug, run_id, created_by))

    monkeypatch.setattr(knowledge_events, "process_ingest_run_and_start_index_sync", _fake_runner)
    handler = knowledge_events.make_knowledge_ingest_pipeline_handler()

    handler({"tenant_slug": "demo", "run_id": "run-1", "created_by": 5})

    assert calls == [("demo", "run-1", 5)]


def test_enqueue_ingest_pipeline_job_uses_outbox_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[tuple[str, dict, str | None]] = []

    class _Channel:
        def publish(self, event_type: str, payload: dict, *, idempotency_key: str | None = None) -> None:
            published.append((event_type, payload, idempotency_key))

    monkeypatch.setattr(knowledge_background_jobs, "get_module_service", lambda _name: _Channel())

    knowledge_background_jobs.enqueue_ingest_pipeline_job(
        tenant_slug="demo",
        run_id="run-2",
        created_by=7,
        facade=object(),
    )

    assert published[0][0] == "knowledge.ingest_pipeline"
    assert published[0][1]["run_id"] == "run-2"


def test_enqueue_index_build_job_uses_outbox_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[tuple[str, dict, str | None]] = []

    class _Channel:
        def publish(self, event_type: str, payload: dict, *, idempotency_key: str | None = None) -> None:
            published.append((event_type, payload, idempotency_key))

    monkeypatch.setattr(knowledge_background_jobs, "get_module_service", lambda _name: _Channel())

    knowledge_background_jobs.enqueue_index_build_job(tenant_slug="demo", build_id="build-1")

    assert published[0][0] == "knowledge.index_build"
    assert published[0][1]["build_id"] == "build-1"

