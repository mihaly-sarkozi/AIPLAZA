# backend/core/modules/tenant/ports.py
# Feladat: A tenant modul service és adapter határait leíró Protocol portokat tartalmazza. Repository, schema manager, user provisioning és domain verification szerződéseket rögzít, hogy a magasabb szintű use case-ek ne konkrét adapterekre épüljenek. Tenant contract réteg.
# Sárközi Mihály - 2026.05.21

"""Tenant extension port interfészek.

Minden Protocol itt van definiálva – ezek a core tenant réteg és a külső
extension implementációk közti tiszta elválasztást adják.

Dependency irány: core/modules/tenant → ports (Protocol-ok, nincs implementáció)
                  külső implementációk → implementálják a Protocol-okat
"""
from __future__ import annotations

from typing import Protocol

from core.modules.tenant.dto import TenantSnapshot


class TenantUserProvisioningPort(Protocol):
    @property
    def user_repository(self):
        ...

    def create(
        self,
        *,
        email: str,
        name: str | None = None,
        role: str = "user",
        request_base_url: str | None = None,
        created_by: int | None = None,
        send_invite_email: bool = True,
        activate_immediately: bool = False,
    ):
        ...


class TenantReadRepositoryPort(Protocol):
    def get_by_slug(self, slug: str):
        ...

    def get_config_by_tenant_id(self, tenant_id: int, *, slug: str):
        ...

    def get_domain(self, domain: str | None):
        ...

    def get_actor_user_id(self, tenant_id: int) -> int | None:
        ...

    def get_tenant_status(self, slug: str):
        ...

    def get_snapshot_by_slug(self, slug: str) -> TenantSnapshot | None:
        ...


class TenantWriteRepositoryPort(Protocol):
    def create(self, slug: str, name: str, *, created_by: int | None = None, is_active: bool = False):
        ...

    def delete_by_slug(self, slug: str) -> None:
        ...

    def create_config(
        self,
        tenant_id: int,
        *,
        slug: str,
        package: str,
        feature_flags: dict,
        limits: dict,
        created_by: int | None = None,
    ) -> None:
        ...

    def delete_config(self, tenant_id: int, *, slug: str) -> None:
        ...

    def create_domain(self, tenant_id: int, domain: str, *, created_by: int | None = None):
        ...

    def delete_domain(self, domain: str, *, tenant_id: int | None = None) -> None:
        ...

    def set_actor(self, tenant_id: int, actor_user_id: int | None, *, updated_by: int | None = None) -> None:
        ...

    def activate(self, tenant_id: int, *, updated_by: int | None = None) -> None:
        ...

    def deactivate(self, tenant_id: int, *, updated_by: int | None = None) -> None:
        ...

    def verify_domain(self, domain: str, *, verified_at=None, updated_by: int | None = None):
        ...


class TenantRepositoryPort(TenantReadRepositoryPort, TenantWriteRepositoryPort, Protocol):
    pass


class TenantSchemaManagerPort(Protocol):
    def exists(self, slug: str) -> bool:
        ...

    def create(self, slug: str) -> None:
        ...

    def drop(self, slug: str) -> None:
        ...

    def list_missing_tables(self, slug: str) -> tuple[str, ...]:
        ...


class TenantKnowledgeBootstrapPort(Protocol):
    def ensure_initial_demo_knowledge_base(self, owner_id: int, locale: str) -> None:
        ...


class KnowledgeBaseCountPort(Protocol):
    """Port a tudásbázis darabszám lekérdezéséhez.

    Implementálja: a tudásbázis szolgáltatás.
    Használja: pl. BillingService resource-limit ellenőrzéshez.

    Billing modulban a query-t raw SQL-lel végezzük, nem ORM-en keresztül,
    hogy ne legyen közvetlen modul-közi importfüggés.
    """

    def count_knowledge_bases(self) -> int:
        ...
