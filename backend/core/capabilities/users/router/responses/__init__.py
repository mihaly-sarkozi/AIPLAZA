from __future__ import annotations

import importlib

__all__ = ["UserResponse"]


def __getattr__(name: str):
    if name == "UserResponse":
        return getattr(importlib.import_module("core.capabilities.users.router.responses.user_response"), "UserResponse")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
