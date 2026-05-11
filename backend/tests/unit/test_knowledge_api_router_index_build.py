from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from apps.knowledge.api import router as knowledge_api_router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_run_index_build_with_retry_retries_once_and_keeps_tenant_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | None, str]] = []

    async def _fake_runner(tenant_slug, callable_obj, build_id):  # type: ignore[no-untyped-def]
        calls.append((tenant_slug, build_id))
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        return None

    monkeypatch.setattr(knowledge_api_router, "run_async_with_tenant_schema", _fake_runner)

    class _Facade:
        async def run_index_build(self, build_id: str) -> None:
            return None

    await knowledge_api_router._run_index_build_with_retry("demo-tenant", _Facade(), "build-123", retries=1)

    assert calls == [("demo-tenant", "build-123"), ("demo-tenant", "build-123")]


@dataclass
class _Corpus:
    uuid: str


@dataclass
class _Run:
    id: str
    status: str
    updated_at: datetime
    started_at: datetime | None = None
    created_at: datetime = datetime.now(timezone.utc)


@dataclass
class _Build:
    id: str
    status: str
    started_at: datetime | None
    created_at: datetime


@dataclass
class _Item:
    id: str
    status: str


class _RecoveryFacade:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        stale = now - timedelta(minutes=40)
        self.failed_runs: list[str] = []
        self.failed_builds: list[str] = []
        self.reprocessed_items: list[str] = []
        self.processed_items: list[str] = []
        self._runs = [_Run(id="run-1", status="processing", updated_at=stale, started_at=stale, created_at=stale)]
        self._builds = [_Build(id="build-1", status="building", started_at=stale, created_at=stale)]

    def list_all_unfiltered(self):  # type: ignore[no-untyped-def]
        return [_Corpus(uuid="kb-1")]

    def list_ingest_runs(self, _corpus_uuid: str, *, limit: int = 50, offset: int = 0):  # type: ignore[no-untyped-def]
        return list(self._runs)

    def list_ingest_items(self, _run_id: str):  # type: ignore[no-untyped-def]
        return [_Item(id="item-1", status="processing")]

    def is_ingest_item_stale_processing(self, _item):  # type: ignore[no-untyped-def]
        return False

    def is_ingest_run_stale(self, run):  # type: ignore[no-untyped-def]
        return run.id == "run-1"

    def mark_ingest_run_failed_as_stale(self, run_id: str, *, reason: str):  # type: ignore[no-untyped-def]
        self.failed_runs.append(f"{run_id}:{reason}")
        return None

    def list_index_builds(self, _corpus_uuid: str):  # type: ignore[no-untyped-def]
        return list(self._builds)

    def is_index_build_stale(self, build):  # type: ignore[no-untyped-def]
        return build.id == "build-1"

    def mark_index_build_failed_as_stale(self, build_id: str, *, reason: str):  # type: ignore[no-untyped-def]
        self.failed_builds.append(f"{build_id}:{reason}")
        return None

    def request_ingest_item_reprocess(self, item_id: str, *, current_user_id: int | None = None):  # type: ignore[no-untyped-def]
        self.reprocessed_items.append(item_id)
        return None

    def process_ingest_item(self, item_id: str):  # type: ignore[no-untyped-def]
        self.processed_items.append(item_id)
        return None


def test_run_recovery_sweep_marks_stale_run_and_build_failed() -> None:
    facade = _RecoveryFacade()

    knowledge_api_router._run_recovery_sweep_for_tenant("demo", facade, current_user_id=11)

    assert len(facade.failed_runs) == 1
    assert "run-1" in facade.failed_runs[0]
    assert len(facade.failed_builds) == 1
    assert "build-1" in facade.failed_builds[0]
