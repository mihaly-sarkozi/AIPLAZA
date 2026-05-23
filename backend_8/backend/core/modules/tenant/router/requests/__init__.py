# backend/core/modules/tenant/router/requests/__init__.py
# Feladat: A tenant router request modellek exportfelülete. A TenantSignupRequest DTO-t adja tovább a tenant router és tesztek számára. Vékony web request contract belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["TenantSignupRequest"]


def __getattr__(name: str):
    if name == "TenantSignupRequest":
        return getattr(
            importlib.import_module("core.modules.tenant.router.requests.tenant_signup_request"),
            "TenantSignupRequest",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
