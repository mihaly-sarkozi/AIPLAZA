# backend/core/modules/tenant/service/signup/__init__.py
# Feladat: Kompatibilitási importútvonal a canonical tenant signup csomag felé. Az új implementáció a signup/ és provisioning/ csomagok alatt él, ez a fájl régi service/signup importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat: canonical package ``core.modules.tenant.signup``.

Új kód: ``from core.modules.tenant.signup import TenantSignupService``.
"""
from __future__ import annotations

import importlib

__all__ = [
    "DemoLoginTokenService",
    "DemoNewSignupUseCase",
    "DemoSignupResendUseCase",
    "DemoSignupResult",
    "DemoSlugReserver",
    "DemoUnsubscribeUseCase",
    "ProvisioningCompensationPlan",
    "TenantProvisioningRequest",
    "TenantProvisioningService",
    "TenantProvisioningValidation",
    "TenantProvisioningValidator",
    "TenantSignupOrchestrator",
    "TenantSignupService",
]

_LAZY: dict[str, tuple[str, str]] = {
    "DemoLoginTokenService": ("core.modules.tenant.tokens.demo_jwt", "DemoLoginTokenService"),
    "DemoNewSignupUseCase": ("core.modules.tenant.signup.new_demo_signup", "DemoNewSignupUseCase"),
    "DemoSignupResendUseCase": ("core.modules.tenant.signup.resend_demo", "DemoSignupResendUseCase"),
    "DemoSignupResult": ("core.modules.tenant.signup.orchestrator_result", "DemoSignupResult"),
    "DemoSlugReserver": ("core.modules.tenant.slug.reservation", "DemoSlugReserver"),
    "DemoUnsubscribeUseCase": ("core.modules.tenant.signup.unsubscribe", "DemoUnsubscribeUseCase"),
    "ProvisioningCompensationPlan": ("core.modules.tenant.provisioning.models", "ProvisioningCompensationPlan"),
    "TenantProvisioningRequest": ("core.modules.tenant.provisioning.models", "TenantProvisioningRequest"),
    "TenantProvisioningService": ("core.modules.tenant.provisioning.provisioner", "TenantProvisioningService"),
    "TenantProvisioningValidation": ("core.modules.tenant.provisioning.models", "TenantProvisioningValidation"),
    "TenantProvisioningValidator": ("core.modules.tenant.provisioning.validator", "TenantProvisioningValidator"),
    "TenantSignupOrchestrator": ("core.modules.tenant.signup.orchestrator", "TenantSignupOrchestrator"),
    "TenantSignupService": ("core.modules.tenant.signup.service", "TenantSignupService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
