# backend/core/modules/tenant/helpers/__init__.py
# Feladat: A tenant helper csomag exportfelülete. Jelenleg a frontend URL képző helperhez biztosít namespace-t, hogy app route-ok tenant-aware linkeket építhessenek. Vékony helper belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = [
    "tenant_frontend_base_url_for_slug",
    "tenant_frontend_base_url_from_request",
]

_LAZY: dict[str, tuple[str, str]] = {
    "tenant_frontend_base_url_for_slug": (
        "core.modules.tenant.helpers.tenant_frontend_url_helper",
        "tenant_frontend_base_url_for_slug",
    ),
    "tenant_frontend_base_url_from_request": (
        "core.modules.tenant.helpers.tenant_frontend_url_helper",
        "tenant_frontend_base_url_from_request",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
