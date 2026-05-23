# backend/core/infrastructure/audit/service/__init__.py
# Feladat: Az audit service csomag lazy exportfelülete. Az AuditService-t csak kérésre importálja, hogy modulok és bootstrap kódok stabil, olcsó importpontot kapjanak. Audit service csomag belépési pont.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

import importlib

__all__ = ["AuditService"]


def __getattr__(name: str):
    if name == "AuditService":
        return getattr(importlib.import_module("core.infrastructure.audit.service.audit_service"), "AuditService")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
