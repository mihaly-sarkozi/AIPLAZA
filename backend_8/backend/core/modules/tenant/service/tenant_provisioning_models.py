# backend/core/modules/tenant/service/tenant_provisioning_models.py
# Feladat: Kompatibilitási importútvonal a provisioning modellek felé. A canonical modellek a provisioning/models.py alatt élnek, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.provisioning.models import (  # noqa: F401
    ProvisioningCompensationPlan,
    TenantProvisioningRequest,
    TenantProvisioningValidation,
)

__all__ = ["ProvisioningCompensationPlan", "TenantProvisioningRequest", "TenantProvisioningValidation"]
