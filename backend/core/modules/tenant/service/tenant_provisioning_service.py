# backend/core/modules/tenant/service/tenant_provisioning_service.py
# Feladat: Kompatibilitási importútvonal a TenantProvisioningService felé. A canonical provisioning service a provisioning/provisioner.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.provisioning.provisioner import (  # noqa: F401
    TenantProvisioningService,
)
from core.modules.tenant.provisioning.models import (  # noqa: F401
    TenantProvisioningRequest,
    TenantProvisioningValidation,
)

__all__ = ["TenantProvisioningRequest", "TenantProvisioningService", "TenantProvisioningValidation"]
