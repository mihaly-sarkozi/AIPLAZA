# Tenant konfig: csomag, feature flag-ek, limitek – cache-elhető, kevesebb DB lekérdezés.
# 2026.03 – Sárközi Mihály

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: int # Tenant azonosító
    slug: str # tenant slug(subdomain név)
    package: str  # pl. "free", "pro", "enterprise"
    feature_flags: dict[str, bool]  # pl. {"sso": True, "api_export": False}
    limits: dict[str, Any]  # pl. {"max_users": 10, "storage_mb": 1024}
