# backend/core/modules/tenant/service/tenant_signup_service.py
# Feladat: Kompatibilitási importútvonal a TenantSignupService és DemoSignupResult felé. A canonical signup service a signup/service.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.signup.service import TenantSignupService  # noqa: F401
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult  # noqa: F401

__all__ = ["DemoSignupResult", "TenantSignupService"]
