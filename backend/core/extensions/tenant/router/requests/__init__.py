from __future__ import annotations

import importlib

__all__ = ["TenantSignupRequest"]


def __getattr__(name: str):
    if name == "TenantSignupRequest":
        return getattr(
            importlib.import_module("core.extensions.tenant.router.requests.tenant_signup_request"),
            "TenantSignupRequest",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
