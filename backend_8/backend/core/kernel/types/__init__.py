# backend/core/kernel/types/__init__.py
# Feladat: A kernel könnyű type alias exportfelülete. Jelenleg a lifecycle, bootstrap és tenant schema hook callable típusokat adja tovább, hogy a manifest és module contract ugyanazokat a típusokat használja. Core type-only csomag, runtime assembly nélkül.
# Sárközi Mihály - 2026.05.21

from core.kernel.types.lifecycle_hook_types import BootstrapHook, LifecycleHook, TenantSchemaRegistrar

__all__ = ["BootstrapHook", "LifecycleHook", "TenantSchemaRegistrar"]
