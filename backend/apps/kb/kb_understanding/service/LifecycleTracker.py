from __future__ import annotations


class LifecycleTracker:
    def mark(self, *, run_id: str, stage: str) -> None:
        _ = (run_id, stage)
