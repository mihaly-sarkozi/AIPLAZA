# backend/core/kernel/lifecycle/__init__.py
# Feladat: A kernel lifecycle csomag lazy exportfelületét adja. Health, liveness, readiness, runtime status response-okat, a LifecycleService-t, a LifecycleState-et és a LifecycleCoreModule-t csak kérésre importálja, hogy a csomag betöltése könnyű maradjon. Core kernel lifecycle belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = [
    "HealthResponse",
    "LifecycleCoreModule",
    "LifecycleService",
    "LifecycleState",
    "LifecycleStatusResponse",
    "LivenessResponse",
    "ReadinessResponse",
]

_LAZY: dict[str, tuple[str, str]] = {
    "HealthResponse": ("core.kernel.lifecycle.health_response", "HealthResponse"),
    "LifecycleCoreModule": ("core.kernel.lifecycle.lifecycle", "LifecycleCoreModule"),
    "LifecycleService": ("core.kernel.lifecycle.lifecycle_service", "LifecycleService"),
    "LifecycleState": ("core.kernel.lifecycle.lifecycle_state", "LifecycleState"),
    "LifecycleStatusResponse": ("core.kernel.lifecycle.lifecycle_status_response", "LifecycleStatusResponse"),
    "LivenessResponse": ("core.kernel.lifecycle.liveness_response", "LivenessResponse"),
    "ReadinessResponse": ("core.kernel.lifecycle.readiness_response", "ReadinessResponse"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
