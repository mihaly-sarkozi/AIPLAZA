from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BillingReadingPolicy:
    """ReadingPolicyPort — tenant usage kvóta és rögzítés a billing service-en keresztül."""

    def check_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        _ = storage_bytes
        billing = self._billing_service()
        if billing is None:
            return
        allowed, message = billing.can_consume_training_chars(tenant, int(char_count or 0))
        if not allowed:
            raise ValueError(message or "Nincs elég tanítási karakterkeret a csomagban.")

    def record_training_usage(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        billing = self._billing_service()
        if billing is None:
            return
        try:
            billing.record_training_ingest(
                tenant,
                char_count=max(0, int(char_count or 0)),
                storage_bytes=max(0, int(storage_bytes or 0)),
            )
        except Exception:
            logger.warning("billing.record_training_ingest failed", exc_info=True)

    def require_training_mfa_if_needed(self, user: object) -> None:
        _ = user

    @staticmethod
    def _billing_service() -> Any | None:
        try:
            from core.kernel.deps.facade import get_service
            from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE

            return get_service(PLATFORM_TENANT_USAGE_SERVICE)
        except Exception:
            logger.debug("kb_ingest.billing_service_unavailable", exc_info=True)
            return None


__all__ = ["BillingReadingPolicy"]
