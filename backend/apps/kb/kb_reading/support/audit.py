from __future__ import annotations

# backend/apps/kb/kb_reading/support/audit.py
# Feladat: Esemény típus konstansok naplózáshoz.
# Sárközi Mihály - 2026.06.07

READ_RUN_CREATED = "read_run_created"
READ_RUN_UPDATED = "read_run_updated"
READ_RUN_COMPLETED = "read_run_completed"

READ_ITEM_QUEUED = "read_item_queued"
READ_ITEM_ACCEPTED = "read_item_accepted"
READ_ITEM_REJECTED = "read_item_rejected"
READ_ITEM_FAILED = "read_item_failed"

STORAGE_WRITE_STARTED = "storage_write_started"
STORAGE_WRITE_COMPLETED = "storage_write_completed"
STORAGE_WRITE_FAILED = "storage_write_failed"

URL_FETCH_STARTED = "url_fetch_started"
URL_FETCH_COMPLETED = "url_fetch_completed"
URL_FETCH_FAILED = "url_fetch_failed"

DUPLICATE_DETECTED = "duplicate_detected"
UNDERSTANDING_REQUESTED = "understanding_requested"

__all__ = [
    "DUPLICATE_DETECTED",
    "READ_ITEM_ACCEPTED",
    "READ_ITEM_FAILED",
    "READ_ITEM_QUEUED",
    "READ_ITEM_REJECTED",
    "READ_RUN_COMPLETED",
    "READ_RUN_CREATED",
    "READ_RUN_UPDATED",
    "STORAGE_WRITE_COMPLETED",
    "STORAGE_WRITE_FAILED",
    "STORAGE_WRITE_STARTED",
    "UNDERSTANDING_REQUESTED",
    "URL_FETCH_COMPLETED",
    "URL_FETCH_FAILED",
    "URL_FETCH_STARTED",
]
