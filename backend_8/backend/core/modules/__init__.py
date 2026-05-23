# Felelosseg: Csomag exportfelulet es lazy importok definicioja.
# Ez a fájl a core modulcsomag exportjait és inicializálási pontjait fogja össze.

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "AuthCoreModule": "core.modules.auth.auth",
    "BrandCoreModule": "core.modules.brand.brand",
    "DomainCoreModule": "core.kernel.domain.module",
    "LifecycleCoreModule": "core.kernel.lifecycle.lifecycle",
    "SettingsCoreModule": "core.modules.settings.settings",
    "TenantCoreModule": "core.modules.tenant.tenant",
    "UsersCoreModule": "core.modules.users.users",
}


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'core.modules' has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))


__all__ = list(_LAZY_EXPORTS.keys())
