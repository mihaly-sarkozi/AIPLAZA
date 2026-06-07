from __future__ import annotations


class ProcessingTraceService:
    def record(self, *, run_id: str, event_type: str, message: str) -> None:
        _ = (run_id, event_type, message)
