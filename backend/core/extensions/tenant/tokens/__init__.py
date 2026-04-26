"""Demo bejelentkezési JWT / aláírás – platform TokenService-re épül."""
from __future__ import annotations

import importlib

__all__ = ["DemoLoginTokenService"]


def __getattr__(name: str):
    if name == "DemoLoginTokenService":
        return getattr(importlib.import_module("core.extensions.tenant.tokens.demo_jwt"), "DemoLoginTokenService")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
