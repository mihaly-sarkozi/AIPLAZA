from __future__ import annotations

import importlib

__all__ = ["CorrelationIdMiddleware", "RequestTimingMiddleware"]

_LAZY: dict[str, tuple[str, str]] = {
    "CorrelationIdMiddleware": (
        "core.kernel.middleware.observability.correlation_id_middleware",
        "CorrelationIdMiddleware",
    ),
    "RequestTimingMiddleware": (
        "core.kernel.middleware.observability.request_timing_middleware",
        "RequestTimingMiddleware",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
