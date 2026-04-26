from __future__ import annotations

import importlib

__all__ = [
    "BrandRepository",
    "BrandResponse",
    "BrandService",
    "BrandUpdateRequest",
    "register_brand_tenant_hooks",
]

_LAZY: dict[str, tuple[str, str]] = {
    "BrandResponse": ("core.platform.brand.dto", "BrandResponse"),
    "BrandUpdateRequest": ("core.platform.brand.dto", "BrandUpdateRequest"),
    "BrandRepository": ("core.platform.brand.repositories", "BrandRepository"),
    "BrandService": ("core.platform.brand.services", "BrandService"),
    "register_brand_tenant_hooks": ("core.platform.brand.tenant_hooks", "register_brand_tenant_hooks"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
