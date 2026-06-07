from __future__ import annotations

# backend/apps/kb/kb_reading/support/metrics.py
# Feladat: Mérőszámok a beolvasás lépéseihez.
# Sárközi Mihály - 2026.06.07

METRIC_READ_RUN_CREATED = "kb.reading.run.created"
METRIC_READ_RUN_COMPLETED = "kb.reading.run.completed"
METRIC_READ_RUN_FAILED = "kb.reading.run.failed"

METRIC_READ_ITEM_ACCEPTED = "kb.reading.item.accepted"
METRIC_READ_ITEM_REJECTED = "kb.reading.item.rejected"
METRIC_READ_ITEM_FAILED = "kb.reading.item.failed"

METRIC_STORAGE_WRITE = "kb.reading.storage.write"
METRIC_STORAGE_DELETE = "kb.reading.storage.delete"

METRIC_URL_FETCH = "kb.reading.url.fetch"
METRIC_DUPLICATE_DETECTED = "kb.reading.duplicate.detected"

METRIC_UNDERSTANDING_REQUESTED = "kb.reading.understanding.requested"


def increment(metric_name: str, value: float = 1.0, **tags: str) -> None:
    """Növeli a megadott mérőszámot."""
    _ = (metric_name, value, tags)


def record_duration(metric_name: str, duration_ms: float, **tags: str) -> None:
    """Rögzíti a művelet időtartamát."""
    _ = (metric_name, duration_ms, tags)


__all__ = [
    "METRIC_DUPLICATE_DETECTED",
    "METRIC_READ_ITEM_ACCEPTED",
    "METRIC_READ_ITEM_FAILED",
    "METRIC_READ_ITEM_REJECTED",
    "METRIC_READ_RUN_COMPLETED",
    "METRIC_READ_RUN_CREATED",
    "METRIC_READ_RUN_FAILED",
    "METRIC_STORAGE_DELETE",
    "METRIC_STORAGE_WRITE",
    "METRIC_UNDERSTANDING_REQUESTED",
    "METRIC_URL_FETCH",
    "increment",
    "record_duration",
]
