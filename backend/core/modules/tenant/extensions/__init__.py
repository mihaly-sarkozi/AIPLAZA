# backend/core/modules/tenant/extensions/__init__.py
# Feladat: A tenant extension csomag exportfelülete. Tenant sign-up hook registry típusokat és regisztrációs helper függvényeket ad tovább app modulok számára. Tenant-specifikus extension contract belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .tenant_hooks import (
    TenantExtensionRegistry,
    TenantProvisioningHook,
    TenantSignupContext,
    TenantSignupHook,
    clear_tenant_signup_hooks,
    get_tenant_extension_registry,
    get_tenant_signup_hooks,
    register_tenant_signup_hook,
)

__all__ = [
    "TenantExtensionRegistry",
    "TenantProvisioningHook",
    "TenantSignupContext",
    "TenantSignupHook",
    "clear_tenant_signup_hooks",
    "get_tenant_extension_registry",
    "get_tenant_signup_hooks",
    "register_tenant_signup_hook",
]
