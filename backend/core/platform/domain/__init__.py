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
    "DomainCreateRequest": ("core.platform.domain.dto", "DomainCreateRequest"),
    "DomainOverviewResponse": ("core.platform.domain.dto", "DomainOverviewResponse"),
    "DomainRecordResponse": ("core.platform.domain.dto", "DomainRecordResponse"),
    "DomainVerifyRequest": ("core.platform.domain.dto", "DomainVerifyRequest"),
    "DomainPolicy": ("core.platform.domain.policies", "DomainPolicy"),
    "DomainRepository": ("core.platform.domain.repositories", "DomainRepository"),
    "DomainService": ("core.platform.domain.services", "DomainService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
