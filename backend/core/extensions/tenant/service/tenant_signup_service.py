# Backward-compat re-export – implementation moved to service/signup/service.py
from core.extensions.tenant.signup.service import TenantSignupService  # noqa: F401
from core.extensions.tenant.signup.orchestrator_result import DemoSignupResult  # noqa: F401

__all__ = ["DemoSignupResult", "TenantSignupService"]
