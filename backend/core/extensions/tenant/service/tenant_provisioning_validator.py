# Backward-compat re-export – implementation moved to service/signup/validator.py
from core.extensions.tenant.provisioning.validator import TenantProvisioningValidator  # noqa: F401

__all__ = ["TenantProvisioningValidator"]
