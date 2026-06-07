from __future__ import annotations

# backend/apps/kb/kb_reading/adapters/noop_event_publisher.py
# Feladat: Ideiglenes ReadingEventPublisher implementáció fejlesztéshez.
# Sárközi Mihály - 2026.06.07

from typing import Any


class NoOpReadingEventPublisher:
    """Esemény kibocsátás nélküli implementáció."""

    def publish_material_read(
        self,
        *,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        raw_ref: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        _ = (knowledge_base_id, read_run_id, read_item_id, raw_ref, metadata)

    def publish_understanding_requested(
        self,
        *,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        raw_ref: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        _ = (knowledge_base_id, read_run_id, read_item_id, raw_ref, metadata)


__all__ = ["NoOpReadingEventPublisher"]
