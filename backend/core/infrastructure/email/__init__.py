# backend/core/infrastructure/email/__init__.py
# Feladat: Az email infrastruktúra csomag lazy exportfelülete. Az EmailService-t és a dev/log preview maszkoló helperét csak kérésre importálja, hogy a bootstrap és modul service-ek stabil, olcsó importpontot kapjanak. Core infrastruktúra email adapter belépési pont.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

import importlib

__all__ = ["EmailService", "mask_email_body_for_log"]

_LAZY: dict[str, tuple[str, str]] = {
    "EmailService": ("core.infrastructure.email.email_service", "EmailService"),
    "mask_email_body_for_log": ("core.infrastructure.email.email_service", "mask_email_body_for_log"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
