# backend/core/kernel/jobs/registry.py
# Feladat: App modulok outbox handler regisztrációja a platform dispatcher-be.
# Sárközi Mihály - 2026.06.07

from __future__ import annotations

from typing import Any, Callable


def register_job_handler(
    dispatcher: Any,
    event_type: str,
    handler: Callable[[dict[str, Any]], None],
) -> None:
    """Egy job típushoz tartozó worker handler bekötése."""
    normalized_type = str(event_type or "").strip()
    if not normalized_type:
        raise ValueError("register_job_handler: event_type is required")
    if not callable(handler):
        raise TypeError("register_job_handler: handler must be callable")
    dispatcher.register(normalized_type, handler)


__all__ = ["register_job_handler"]
