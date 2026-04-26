from __future__ import annotations

import importlib

__all__ = ["get_limiter", "limiter", "refresh_token_key", "user_or_ip_key"]

_LAZY: dict[str, tuple[str, str]] = {
    "get_limiter": ("core.kernel.security.rate_limit.rate_limit_middleware", "get_limiter"),
    "limiter": ("core.kernel.security.rate_limit.rate_limit_middleware", "limiter"),
    "refresh_token_key": ("core.kernel.security.rate_limit.rate_limit_middleware", "refresh_token_key"),
    "user_or_ip_key": ("core.kernel.security.rate_limit.rate_limit_middleware", "user_or_ip_key"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
