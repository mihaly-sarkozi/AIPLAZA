from __future__ import annotations

import importlib

__all__ = ["LoginRequest"]


def __getattr__(name: str):
    if name == "LoginRequest":
        return getattr(
            importlib.import_module("core.capabilities.auth.router.requests.login_request"),
            "LoginRequest",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
