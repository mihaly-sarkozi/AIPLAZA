from __future__ import annotations

import pytest

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.service.ingest_run_service import IngestRunService

pytestmark = pytest.mark.unit


class _RunStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestRun] = {}

    def create(self, run: IngestRun) -> IngestRun:
        self.items[run.id] = run
        return run

    def update(self, run: IngestRun) -> IngestRun:
        self.items[run.id] = run
        return run

    def get(self, run_id: str) -> IngestRun | None:
        return self.items.get(run_id)

    def list_for_corpus(self, corpus_uuid: str, *, limit: int = 20, offset: int = 0) -> list[IngestRun]:
        return []

    def list_recent(self, *, limit: int = 20) -> list[IngestRun]:
        return []

    def count_for_corpus(self, corpus_uuid: str) -> int:
        return 0

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        return 0


class _ItemStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestItem] = {}

    def create_many(self, items: list[IngestItem]) -> list[IngestItem]:
        for item in items:
            self.items[item.id] = item
        return items

    def update(self, item: IngestItem) -> IngestItem:
        self.items[item.id] = item
        return item

    def get(self, item_id: str) -> IngestItem | None:
        return self.items.get(item_id)

    def list_for_run(self, run_id: str) -> list[IngestItem]:
        return [item for item in self.items.values() if item.ingest_run_id == run_id]

    def list_for_corpus(self, corpus_uuid: str) -> list[IngestItem]:
        return [item for item in self.items.values() if item.corpus_uuid == corpus_uuid]

    def find_by_hash(
        self,
        *,
        corpus_uuid: str,
        content_hash: str,
        exclude_item_id: str | None = None,
        pipeline_version: str | None = None,
    ) -> IngestItem | None:
        return None

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        return 0


def _build_service(run_store: _RunStore, item_store: _ItemStore) -> IngestRunService:
    return IngestRunService(
        ingest_run_store=run_store,
        ingest_item_store=item_store,
        progress_summary_builder=lambda run, items: {"status": run.status, "total_items": len(items)},
        quality_diagnostics_builder=lambda items: {"failed": sum(1 for item in items if item.status == "failed")},
    )


def test_ingest_run_service_creates_run() -> None:
    run_store = _RunStore()
    item_store = _ItemStore()
    service = _build_service(run_store, item_store)

    run = service.create_run(
        tenant="demo",
        corpus_uuid="kb-1",
        input_channel="file",
        batch_size=2,
        pipeline_route="source_parser",
        created_by=11,
        metadata={"input_types": ["file"]},
    )

    assert run.status == "queued"
    assert run.queued_count == 2
    assert run.batch_size == 2


def test_ingest_run_service_marks_processing_failed_and_retry() -> None:
    run_store = _RunStore()
    item_store = _ItemStore()
    service = _build_service(run_store, item_store)
    item = IngestItem(ingest_run_id="run-1", tenant="demo", corpus_uuid="kb-1", status="queued")
    item_store.create_many([item])

    processing = service.mark_item_processing(item, progress_message="processing")
    assert processing.status == "processing"
    assert processing.lease_owner == "outbox-worker"

    failed = service.mark_item_failed(
        processing,
        error_code="processing_failed",
        error_message="boom",
        progress_message="failed",
    )
    assert failed.status == "failed"
    assert failed.retry_count == 1

    retry = service.mark_item_retry(failed)
    assert retry.status == "queued"
    assert retry.lease_owner is None


def test_ingest_run_service_recalculates_progress_and_completion() -> None:
    run_store = _RunStore()
    item_store = _ItemStore()
    service = _build_service(run_store, item_store)
    run = run_store.create(
        IngestRun(
            tenant="demo",
            corpus_uuid="kb-1",
            input_channel="file",
            status="processing",
            batch_size=2,
        )
    )
    item_store.create_many(
        [
            IngestItem(ingest_run_id=run.id, tenant="demo", corpus_uuid="kb-1", status="completed"),
            IngestItem(ingest_run_id=run.id, tenant="demo", corpus_uuid="kb-1", status="failed"),
        ]
    )

    refreshed = service.recalculate_progress(run.id)
    assert refreshed.status == "partial_success"
    assert refreshed.completed_count == 1
    assert refreshed.failed_count == 1

    completed = service.mark_run_completed_if_ready(run.id)
    assert completed.status == "partial_success"
