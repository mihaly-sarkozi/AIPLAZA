# backend/core/modules/tenant/service/tenant_provisioning_validator.py
# Feladat: Kompatibilitási importútvonal a TenantProvisioningValidator felé. A canonical validator a provisioning/validator.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.provisioning.validator import TenantProvisioningValidator  # noqa: F401

__all__ = ["TenantProvisioningValidator"]
