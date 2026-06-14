from __future__ import annotations

from datetime import datetime, timezone

from apps.kb.kb_processing.adapters.ProcessingEventReaderAdapter import ProcessingEventReaderAdapter
from apps.kb.kb_processing.orm.ProcessingEvent import ProcessingEvent


class _FakeEventRepository:
    def __init__(self, rows: list[ProcessingEvent]) -> None:
        self._rows = rows

    def list_for_job(self, job_id: str, *, module: str | None = None, limit: int = 500) -> list[ProcessingEvent]:
        rows = [row for row in self._rows if row.job_id == job_id]
        if module:
            rows = [row for row in rows if row.module == module]
        return rows


def _event(
    *,
    step: str,
    status: str,
    duration_ms: int | None = None,
    message: str | None = None,
    metadata: dict | None = None,
    created_at: datetime | None = None,
) -> ProcessingEvent:
    return ProcessingEvent(
        id=f"evt_{step}_{status}",
        tenant_slug="tenant1",
        knowledge_base_id="kb-1",
        training_batch_id="batch-1",
        training_item_id="item-1",
        job_id="job-1",
        module="kb_understanding",
        stage="understanding",
        step=step,
        event_type="step_completed",
        status=status,
        message=message,
        duration_ms=duration_ms,
        input_summary_json={"chars": 10},
        output_summary_json={"chunks": 2},
        metadata_json=dict(metadata or {}),
        created_at=created_at or datetime(2026, 6, 13, 10, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None),
    )


def test_list_for_job_returns_only_latest_terminal_event_per_step():
    adapter = ProcessingEventReaderAdapter(
        _FakeEventRepository(
            [
                _event(step="extract", status="STARTED", created_at=datetime(2026, 6, 13, 10, 0, 0)),
                _event(
                    step="extract",
                    status="COMPLETED",
                    duration_ms=120,
                    created_at=datetime(2026, 6, 13, 10, 0, 1),
                ),
                _event(step="extract", status="STARTED", created_at=datetime(2026, 6, 13, 10, 1, 0)),
                _event(
                    step="extract",
                    status="COMPLETED",
                    duration_ms=95,
                    created_at=datetime(2026, 6, 13, 10, 1, 5),
                ),
                _event(
                    step="chunk",
                    status="FAILED",
                    duration_ms=40,
                    message="chunk failed",
                    metadata={"error_code": "CHUNK_EMPTY"},
                    created_at=datetime(2026, 6, 13, 10, 2, 0),
                ),
            ]
        )
    )

    views = adapter.list_for_job("job-1", module="kb_understanding")

    assert [view.step for view in views] == ["extract", "chunk"]
    assert views[0].status == "completed"
    assert views[0].duration_ms == 95
    assert views[1].status == "failed"
    assert views[1].error_code == "CHUNK_EMPTY"
    assert views[1].error_message == "chunk failed"
