from __future__ import annotations

from typing import Any


class RetrievalFeedbackService:
    """Feedback capture és trace lekérés a retrieval pipeline-hoz."""

    def __init__(self, retrieval_service: Any) -> None:
        self.retrieval_service = retrieval_service

    def capture_feedback(
        self,
        trace_id: str,
        helpful: bool | None = None,
        context_useful: bool | None = None,
        wrong_entity_resolution: bool = False,
        wrong_time_slice: bool = False,
        note: str | None = None,
    ) -> dict:
        return self.retrieval_service.capture_feedback(
            trace_id=trace_id,
            helpful=helpful,
            context_useful=context_useful,
            wrong_entity_resolution=wrong_entity_resolution,
            wrong_time_slice=wrong_time_slice,
            note=note,
        )

    def list_feedback(self, limit: int = 100) -> list[dict]:
        return self.retrieval_service.list_feedback(limit=limit)

    def list_traces(self, limit: int = 100) -> list[dict]:
        return self.retrieval_service.list_traces(limit=limit)
