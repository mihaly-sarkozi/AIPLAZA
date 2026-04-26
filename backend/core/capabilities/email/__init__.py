from __future__ import annotations

import importlib

__all__ = ["EmailService", "mask_email_body_for_log"]

_LAZY: dict[str, tuple[str, str]] = {
    "EmailService": ("core.capabilities.email.email_service", "EmailService"),
    "mask_email_body_for_log": ("core.capabilities.email.email_service", "mask_email_body_for_log"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
