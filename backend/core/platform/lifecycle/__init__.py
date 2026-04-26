from __future__ import annotations

import importlib

__all__ = [
    "HealthResponse",
    "LifecycleService",
    "LifecycleState",
    "LifecycleStatusResponse",
    "LivenessResponse",
    "ReadinessResponse",
]

_LAZY: dict[str, tuple[str, str]] = {
    "HealthResponse": ("core.platform.lifecycle.dto", "HealthResponse"),
    "LifecycleStatusResponse": ("core.platform.lifecycle.dto", "LifecycleStatusResponse"),
    "LivenessResponse": ("core.platform.lifecycle.dto", "LivenessResponse"),
    "ReadinessResponse": ("core.platform.lifecycle.dto", "ReadinessResponse"),
    "LifecycleState": ("core.platform.lifecycle.models", "LifecycleState"),
    "LifecycleService": ("core.platform.lifecycle.services", "LifecycleService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
