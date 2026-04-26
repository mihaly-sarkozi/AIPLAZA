from __future__ import annotations

import importlib

__all__ = ["AuditLogORM"]


def __getattr__(name: str):
    if name == "AuditLogORM":
        return getattr(importlib.import_module("core.capabilities.audit.models.audit_log_orm"), "AuditLogORM")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
