"""Backward-compat: canonical package ``core.extensions.tenant.signup``.

Új kód: ``from core.extensions.tenant.signup import TenantSignupService``.
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
    "DemoLoginTokenService": ("core.extensions.tenant.tokens.demo_jwt", "DemoLoginTokenService"),
    "DemoNewSignupUseCase": ("core.extensions.tenant.signup.new_demo_signup", "DemoNewSignupUseCase"),
    "DemoSignupResendUseCase": ("core.extensions.tenant.signup.resend_demo", "DemoSignupResendUseCase"),
    "DemoSignupResult": ("core.extensions.tenant.signup.orchestrator_result", "DemoSignupResult"),
    "DemoSlugReserver": ("core.extensions.tenant.slug.reservation", "DemoSlugReserver"),
    "DemoUnsubscribeUseCase": ("core.extensions.tenant.signup.unsubscribe", "DemoUnsubscribeUseCase"),
    "ProvisioningCompensationPlan": ("core.extensions.tenant.provisioning.models", "ProvisioningCompensationPlan"),
    "TenantProvisioningRequest": ("core.extensions.tenant.provisioning.models", "TenantProvisioningRequest"),
    "TenantProvisioningService": ("core.extensions.tenant.provisioning.provisioner", "TenantProvisioningService"),
    "TenantProvisioningValidation": ("core.extensions.tenant.provisioning.models", "TenantProvisioningValidation"),
    "TenantProvisioningValidator": ("core.extensions.tenant.provisioning.validator", "TenantProvisioningValidator"),
    "TenantSignupOrchestrator": ("core.extensions.tenant.signup.orchestrator", "TenantSignupOrchestrator"),
    "TenantSignupService": ("core.extensions.tenant.signup.service", "TenantSignupService"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
