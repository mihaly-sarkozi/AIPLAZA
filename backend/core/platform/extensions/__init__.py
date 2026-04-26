"""Platform extension registry exports."""
from __future__ import annotations

from core.platform.extensions.tenant_hooks import (
    TenantExtensionRegistry,
    TenantSignupContext,
    TenantSignupHook,
    clear_tenant_signup_hooks,
    get_tenant_extension_registry,
    get_tenant_signup_hooks,
    register_tenant_signup_hook,
)

__all__ = [
    "TenantExtensionRegistry",
    "TenantSignupContext",
    "TenantSignupHook",
    "clear_tenant_signup_hooks",
    "get_tenant_extension_registry",
    "get_tenant_signup_hooks",
    "register_tenant_signup_hook",
]

