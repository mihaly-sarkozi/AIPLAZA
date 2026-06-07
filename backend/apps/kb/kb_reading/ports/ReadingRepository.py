from __future__ import annotations

from typing import Protocol

from apps.kb.kb_reading.domain.ReadEvent import ReadEvent
from apps.kb.kb_reading.domain.ReadItem import ReadItem
from apps.kb.kb_reading.domain.ReadRun import ReadRun


class ReadingRepository(Protocol):
    def create_run(self, run: ReadRun) -> ReadRun: ...

    def update_run(self, run: ReadRun) -> ReadRun: ...

    def get_run(self, run_id: str) -> ReadRun | None: ...

    def list_runs_for_kb(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReadRun]: ...

    def create_item(self, item: ReadItem) -> ReadItem: ...

    def update_item(self, item: ReadItem) -> ReadItem: ...

    def get_item(self, item_id: str) -> ReadItem | None: ...

    def list_items_for_run(self, read_run_id: str) -> list[ReadItem]: ...

    def create_event(self, event: ReadEvent) -> ReadEvent: ...

    def list_events_for_run(self, read_run_id: str) -> list[ReadEvent]: ...

    def find_duplicate_by_idempotency_key(
        self,
        knowledge_base_id: str,
        idempotency_key: str,
    ) -> ReadItem | None: ...

    def find_latest_url_item(
        self,
        knowledge_base_id: str,
        origin_url: str,
    ) -> ReadItem | None: ...


__all__ = ["ReadingRepository"]
