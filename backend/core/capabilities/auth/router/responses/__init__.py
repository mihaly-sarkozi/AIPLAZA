from __future__ import annotations

import importlib

__all__ = ["TokenResponse", "TwoFactorRequiredResponse"]

_LAZY: dict[str, tuple[str, str]] = {
    "TokenResponse": (
        "core.capabilities.auth.router.responses.token_response",
        "TokenResponse",
    ),
    "TwoFactorRequiredResponse": (
        "core.capabilities.auth.router.responses.two_factor_required_response",
        "TwoFactorRequiredResponse",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
