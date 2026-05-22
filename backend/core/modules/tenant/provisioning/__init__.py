# backend/core/modules/tenant/provisioning/__init__.py
# Feladat: A tenant provisioning csomag lazy exportfelülete. Provisioning request, validation, compensation modelleket, validatort és provisioning service-t ad tovább. Canonical provisioning belépési pont új tenant létrehozási folyamatokhoz.
# Sárközi Mihály - 2026.05.21

"""Tenant provisioning alrendszer: modell, validátor, provisioner (kompenzációs lépésekkel).

Extension point: új tenant artefaktumokhoz a ``TenantProvisioningService`` bővíthető;
hookokhoz lásd ``tenant.schema.hooks``.
"""
from __future__ import annotations

import importlib

__all__ = [
    "ProvisioningCompensationPlan",
    "TenantProvisioningRequest",
    "TenantProvisioningService",
    "TenantProvisioningValidation",
    "TenantProvisioningValidator",
]

_LAZY: dict[str, tuple[str, str]] = {
    "ProvisioningCompensationPlan": ("core.modules.tenant.provisioning.models", "ProvisioningCompensationPlan"),
    "TenantProvisioningRequest": ("core.modules.tenant.provisioning.models", "TenantProvisioningRequest"),
    "TenantProvisioningValidation": ("core.modules.tenant.provisioning.models", "TenantProvisioningValidation"),
    "TenantProvisioningService": ("core.modules.tenant.provisioning.provisioner", "TenantProvisioningService"),
    "TenantProvisioningValidator": ("core.modules.tenant.provisioning.validator", "TenantProvisioningValidator"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
