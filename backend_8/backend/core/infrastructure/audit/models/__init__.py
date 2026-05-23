# backend/core/infrastructure/audit/models/__init__.py
# Feladat: Az audit ORM modellek lazy exportfelülete. Az AuditLogORM modellt csak kérésre importálja, hogy az audit csomag betöltése ne húzza be azonnal a tenant-sémás SQLAlchemy modellt. Audit model csomag belépési pont.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

import importlib

__all__ = ["AuditLogORM"]


def __getattr__(name: str):
    if name == "AuditLogORM":
        return getattr(importlib.import_module("core.infrastructure.audit.models.audit_log_orm"), "AuditLogORM")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
