# backend/core/infrastructure/audit/repositories/__init__.py
# Feladat: Az audit repository csomag lazy exportfelülete. Az AuditLogRepository adaptert csak kérésre importálja, hogy a bootstrap és service réteg stabil importpontot kapjon. Audit repository csomag belépési pont.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

import importlib

__all__ = ["AuditLogRepository"]


def __getattr__(name: str):
    if name == "AuditLogRepository":
        return getattr(
            importlib.import_module("core.infrastructure.audit.repositories.audit_log_repository"),
            "AuditLogRepository",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
