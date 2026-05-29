# backend/core/modules/tenant/provisioning/models.py
# Feladat: A tenant provisioning request, validation és compensation modelleket definiálja. A provisioning folyamat inputját, validációs eredményeit és részleges hiba esetén visszagörgetendő erőforrásokat írja le. Provisioning adatcontract réteg.
# Sárközi Mihály - 2026.05.21

"""Data models for tenant provisioning.

Pure dataclasses – no I/O, no framework dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TenantProvisioningRequest:
    slug: str
    tenant_name: str
    owner_email: str
    owner_name: str | None
    primary_domain: str
    custom_domain: str | None = None
    package: str = "free"
    feature_flags: dict | None = None
    limits: dict | None = None
    owner_send_invite_email: bool = True
    owner_activate_immediately: bool = False
    owner_invite_lang: str | None = None


@dataclass(frozen=True)
class TenantProvisioningValidation:
    tenant_exists: bool
    owner_exists: bool
    config_exists: bool
    primary_domain_exists: bool
    custom_domain_exists: bool
    schema_exists: bool
    missing_schema_tables: tuple[str, ...] = ()

    @property
    def is_consistent(self) -> bool:
        return (
            self.tenant_exists
            and self.owner_exists
            and self.config_exists
            and self.primary_domain_exists
            and self.schema_exists
            and not self.missing_schema_tables
            and self.custom_domain_exists is not False
        )


@dataclass
class ProvisioningCompensationPlan:
    schema_created: bool = False
    tenant_created: bool = False
    actor_changed: bool = False
    previous_actor_user_id: int | None = None
    config_created: bool = False
    domains_created: list[str] = field(default_factory=list)


__all__ = [
    "ProvisioningCompensationPlan",
    "TenantProvisioningRequest",
    "TenantProvisioningValidation",
]
