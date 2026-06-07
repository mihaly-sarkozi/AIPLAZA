# backend/core/kernel/jobs/errors.py
# Feladat: Job queue (outbox) enqueue hibák — app-specifikus wrapperek ezt fordíthatják HTTP-re.
# Sárközi Mihály - 2026.06.07

from __future__ import annotations


class JobQueueUnavailableError(RuntimeError):
    """A platform outbox queue nem elérhető vagy elutasította a jobot."""

    def __init__(self, message: str = "Platform job queue is not available.") -> None:
        super().__init__(message)


__all__ = ["JobQueueUnavailableError"]
