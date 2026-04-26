"""HTTP edge védelem: auth middleware, CSRF, security headerek, user cache.

Csak kérésszintű / technikai védelmek; token kiadás, audience, jogosultság
policy és üzleti auth szabályok a `core.platform.auth` modulban vannak.
"""

from __future__ import annotations

import importlib

__all__ = ["AuthMiddleware", "CSRFMiddleware", "SecurityHeadersMiddleware", "invalidate_user_cache"]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthMiddleware": ("core.kernel.middleware.security.auth_middleware", "AuthMiddleware"),
    "CSRFMiddleware": ("core.kernel.middleware.security.csrf_middleware", "CSRFMiddleware"),
    "SecurityHeadersMiddleware": (
        "core.kernel.middleware.security.security_headers_middleware",
        "SecurityHeadersMiddleware",
    ),
    "invalidate_user_cache": ("core.kernel.middleware.security.user_cache", "invalidate_user_cache"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
