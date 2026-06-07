from __future__ import annotations

# backend/apps/kb/kb_reading/service/ReadRunService.py
# Feladat: Beolvasási futások lekérdezése és listázása.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_reading.dto.ReadRunDetailResponse import ReadRunDetailResponse
from apps.kb.kb_reading.dto.ReadRunListResponse import ReadRunListResponse
from apps.kb.kb_reading.ports.ReadingRepository import ReadingRepository
from apps.kb.kb_reading.service.ReadingResponseMapper import (
    to_event_response,
    to_item_response,
    to_run_response,
)
from apps.kb.shared.errors import KbNotFoundError


class ReadRunService:
    """Beolvasási futások olvasási műveletei."""

    def __init__(self, *, repository: ReadingRepository) -> None:
        self._repository = repository

    def list_runs(
        self,
        *,
        knowledge_base_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ReadRunListResponse:
        """Listázza a futásokat egy tudástárhoz."""
        safe_limit = max(1, min(int(limit or 20), 50))
        safe_offset = max(0, int(offset or 0))
        runs = self._repository.list_runs_for_kb(
            knowledge_base_id,
            limit=safe_limit,
            offset=safe_offset,
        )
        return ReadRunListResponse(
            items=[to_run_response(run) for run in runs],
            total=len(runs),
        )

    def get_detail(self, run_id: str) -> ReadRunDetailResponse:
        """Lekéri a futás részletes adatait."""
        run = self._repository.get_run(run_id)
        if run is None:
            raise KbNotFoundError("Read run not found.")
        items = self._repository.list_items_for_run(run_id)
        events = self._repository.list_events_for_run(run_id)
        return ReadRunDetailResponse(
            run=to_run_response(run),
            items=[to_item_response(item) for item in items],
            events=[to_event_response(event) for event in events],
        )


__all__ = ["ReadRunService"]
