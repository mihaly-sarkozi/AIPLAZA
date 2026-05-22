# backend/core/modules/tenant/service/tenant_signup_orchestrator.py
# Feladat: Kompatibilitási importútvonal a TenantSignupOrchestrator felé. A canonical orchestrator a signup/orchestrator.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.signup.orchestrator import (  # noqa: F401
    TenantSignupOrchestrator,
)
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult  # noqa: F401

__all__ = ["DemoSignupResult", "TenantSignupOrchestrator"]
