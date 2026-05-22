# backend/core/kernel/domain/__init__.py
# Feladat: A kernel domain routing és custom domain kezelés lazy exportfelülete. DTO-kat, DomainPolicy-t, DomainRepository-t és DomainService-t csak kérésre importál, hogy a domain routing réteg olcsón és runtime assembly nélkül betölthető legyen. Core kernel domain belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = [
    "DomainCreateRequest",
    "DomainOverviewResponse",
    "DomainPolicy",
    "DomainRecordResponse",
    "DomainRepository",
    "DomainService",
    "DomainVerifyRequest",
]

_LAZY: dict[str, tuple[str, str]] = {
    "DomainCreateRequest": ("core.kernel.domain.dto", "DomainCreateRequest"),
    "DomainOverviewResponse": ("core.kernel.domain.dto", "DomainOverviewResponse"),
    "DomainRecordResponse": ("core.kernel.domain.dto", "DomainRecordResponse"),
    "DomainVerifyRequest": ("core.kernel.domain.dto", "DomainVerifyRequest"),
    "DomainPolicy": ("core.kernel.domain.policies", "DomainPolicy"),
    "DomainRepository": ("core.kernel.domain.repositories", "DomainRepository"),
    "DomainService": ("core.kernel.domain.services", "DomainService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
