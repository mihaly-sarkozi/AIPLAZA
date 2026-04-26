from __future__ import annotations

import importlib

__all__ = ["AuditService"]


def __getattr__(name: str):
    if name == "AuditService":
        return getattr(importlib.import_module("core.capabilities.audit.service.audit_service"), "AuditService")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
