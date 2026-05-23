from __future__ import annotations

import pytest

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.ingest_run import IngestRun
from tests.unit.test_app_knowledge_facade import _build_facade


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _CaptureRunStore:
    def __init__(self, run: IngestRun) -> None:
        self._run = run
        self.updated: list[IngestRun] = []

    def get(self, run_id: str) -> IngestRun | None:
        if run_id != self._run.id:
            return None
        return self._run

    def update(self, run: IngestRun) -> IngestRun:
        self._run = run
        self.updated.append(run)
        return run


class _FakeLoop:
    def __init__(self) -> None:
        self.created_task_count = 0

    def create_task(self, coro):  # type: ignore[no-untyped-def]
        self.created_task_count += 1
        coro.close()
        return object()


@pytest.mark.anyio
async def test_auto_refresh_semantic_index_schedules_background_build_once(monkeypatch: pytest.MonkeyPatch) -> None:
    run = IngestRun(id="run-worker-1", tenant="demo", corpus_uuid="kb-1", status="completed", created_by=11, metadata={})
    run_store = _CaptureRunStore(run)
    facade = _build_facade()
    facade._ingest_run_store = run_store
    facade._load_existing_semantic_blocks = lambda **_kwargs: [{"id": "block-1"}]
    scheduled: list[dict[str, object]] = []

    def _schedule(**kwargs):  # type: ignore[no-untyped-def]
        scheduled.append(dict(kwargs))
        return IndexBuild(
            id="build-worker-1",
            tenant="demo",
            corpus_uuid="kb-1",
            index_profile_key="basic_chunk_v1",
            collection_name="kb_kb-1__basic_chunk_v1",
            status="pending",
            metadata={},
        )

    facade.schedule_index_build = _schedule  # type: ignore[method-assign]
    fake_loop = _FakeLoop()
    monkeypatch.setattr("apps.knowledge.service.knowledge_facade.asyncio.get_running_loop", lambda: fake_loop)

    facade._auto_refresh_semantic_block_index_after_ingest(run)

    assert len(scheduled) == 1
    assert fake_loop.created_task_count == 1
    assert run_store.updated
    latest = run_store.updated[-1]
    assert latest.metadata["semantic_block_auto_index_status"] == "scheduled"
    assert latest.metadata["semantic_block_auto_index_build_id"] == "build-worker-1"


def test_auto_refresh_semantic_index_skips_when_already_scheduled() -> None:
    run = IngestRun(
        id="run-worker-2",
        tenant="demo",
        corpus_uuid="kb-1",
        status="completed",
        created_by=11,
        metadata={"semantic_block_auto_index_status": "scheduled"},
    )
    facade = _build_facade()
    facade._ingest_run_store = _CaptureRunStore(run)
    facade._load_existing_semantic_blocks = lambda **_kwargs: [{"id": "block-1"}]
    called = {"schedule": 0}

    def _schedule(**_kwargs):  # type: ignore[no-untyped-def]
        called["schedule"] += 1
        raise AssertionError("schedule_index_build should not be called when already scheduled")

    facade.schedule_index_build = _schedule  # type: ignore[method-assign]
    facade._auto_refresh_semantic_block_index_after_ingest(run)

    assert called["schedule"] == 0
