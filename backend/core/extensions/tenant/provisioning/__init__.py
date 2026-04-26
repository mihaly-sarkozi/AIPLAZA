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
    "ProvisioningCompensationPlan": ("core.extensions.tenant.provisioning.models", "ProvisioningCompensationPlan"),
    "TenantProvisioningRequest": ("core.extensions.tenant.provisioning.models", "TenantProvisioningRequest"),
    "TenantProvisioningValidation": ("core.extensions.tenant.provisioning.models", "TenantProvisioningValidation"),
    "TenantProvisioningService": ("core.extensions.tenant.provisioning.provisioner", "TenantProvisioningService"),
    "TenantProvisioningValidator": ("core.extensions.tenant.provisioning.validator", "TenantProvisioningValidator"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
