# backend/core/kernel/jobs/__init__.py
# Feladat: Platform szintű háttérfeladat (outbox) queue publikus API-ja.
# App modulok ide írnak jobot; a worker a core/kernel/events outbox infrastruktúrát használja.
# Sárközi Mihály - 2026.06.07

from __future__ import annotations

import importlib

__all__ = [
    "JobQueueUnavailableError",
    "enqueue_job",
    "register_job_handler",
]

_LAZY: dict[str, tuple[str, str]] = {
    "JobQueueUnavailableError": ("core.kernel.jobs.errors", "JobQueueUnavailableError"),
    "enqueue_job": ("core.kernel.jobs.enqueue", "enqueue_job"),
    "register_job_handler": ("core.kernel.jobs.registry", "register_job_handler"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
