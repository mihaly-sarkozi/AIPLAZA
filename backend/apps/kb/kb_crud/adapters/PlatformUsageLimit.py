from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/PlatformUsageLimit.py
# Feladat: UsageLimitInterface adapter — a platform tenant usage service-re delegál.
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PlatformUsageLimit:
    def can_create_kb(self, tenant: Any) -> tuple[bool, str | None]:
        try:
            from core.kernel.deps.facade import get_service
            from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE

            usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
        except Exception:
            logger.debug("kb_crud.usage_service_unavailable", exc_info=True)
            return True, None
        return usage_service.can_create_kb(tenant)


__all__ = ["PlatformUsageLimit"]
