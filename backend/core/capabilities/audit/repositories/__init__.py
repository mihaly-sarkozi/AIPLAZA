from __future__ import annotations

import importlib

__all__ = ["AuditLogRepository"]


def __getattr__(name: str):
    if name == "AuditLogRepository":
        return getattr(
            importlib.import_module("core.capabilities.audit.repositories.audit_log_repository"),
            "AuditLogRepository",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
