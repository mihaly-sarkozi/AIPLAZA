# Backward-compat re-export – implementation moved to service/signup/orchestrator.py
from core.extensions.tenant.signup.orchestrator import (  # noqa: F401
    TenantSignupOrchestrator,
)
from core.extensions.tenant.signup.orchestrator_result import DemoSignupResult  # noqa: F401

__all__ = ["DemoSignupResult", "TenantSignupOrchestrator"]
