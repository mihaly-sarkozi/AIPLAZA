# Ez a fájl a(z) apps/features/chat/router csomag exportjait és inicializálási pontjait fogja össze.
from __future__ import annotations

import importlib

__all__ = ["channel_credentials_router", "channel_router", "chat_router"]


def __getattr__(name: str):
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
