from __future__ import annotations

import pytest

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from tests.unit.test_app_knowledge_facade import (
    _InMemoryIngestItemStore,
    _InMemoryIngestRunStore,
    _build_facade,
)


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_progress_summary_contract_contains_required_fields() -> None:
    facade = _build_facade()
    run_store = _InMemoryIngestRunStore()
    item_store = _InMemoryIngestItemStore()
    facade._ingest_run_store = run_store
    facade._ingest_item_store = item_store

    run = run_store.create(IngestRun(id="run-progress-1", corpus_uuid="kb-1", status="processing"))
    item_store.create(
        IngestItem(
            id="item-progress-1",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=1,
            display_name="doc.pdf",
            status="processing",
            progress_message="Mondatértelmezés folyamatban.",
            metadata={
                "processing_summary": {
                    "modules": {
                        "sentence_interpretation": {
                            "key": "sentence_interpretation",
                            "status": "processing",
                            "label": "Mondatértelmezés",
                            "progress_percent": 40,
                            "message": "4 / 10 mondat értelmezve.",
                        }
                    },
                    "document_progress": {
                        "phase": "sentence_interpretation",
                        "progress_percent": 40,
                        "label": "4 / 10 mondat kész",
                    },
                }
            },
        )
    )

    refreshed = facade._refresh_ingest_run(run.id)
    summary = refreshed.metadata["progress_summary"]

    assert isinstance(summary["overall_percent"], int)
    assert summary["overall_percent"] >= 0
    assert summary["overall_percent"] <= 100
    assert summary["active_item_id"] == "item-progress-1"
    assert summary["active_module"] == "sentence_interpretation"
    assert summary["active_message"] == "4 / 10 mondat értelmezve."


def test_progress_summary_contract_reports_full_completion_for_terminal_items() -> None:
    facade = _build_facade()
    run_store = _InMemoryIngestRunStore()
    item_store = _InMemoryIngestItemStore()
    facade._ingest_run_store = run_store
    facade._ingest_item_store = item_store

    run = run_store.create(IngestRun(id="run-progress-2", corpus_uuid="kb-1", status="processing"))
    item_store.create(
        IngestItem(
            id="item-progress-ok",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=1,
            display_name="ok.txt",
            status="completed",
        )
    )
    item_store.create(
        IngestItem(
            id="item-progress-failed",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=2,
            display_name="failed.txt",
            status="failed",
            error_message="parser error",
        )
    )

    refreshed = facade._refresh_ingest_run(run.id)
    summary = refreshed.metadata["progress_summary"]

    assert summary["overall_percent"] == 100
    assert refreshed.status == "partial_success"
    assert refreshed.completed_count == 1
    assert refreshed.failed_count == 1
