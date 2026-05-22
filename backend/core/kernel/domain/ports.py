# backend/core/kernel/domain/ports.py
# Feladat: A DomainService által elvárt repository és verification portokat definiálja. A service ezekre a Protocolokra épít, így a tenant repository adapter és DNS verification szolgáltatás cserélhető marad. Kernel domain contract réteg a service és adapterek között.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DomainRepositoryPort(Protocol):
    def get_tenant_by_slug(self, slug: str): ...

    def list_domains_for_tenant(self, tenant_id: int): ...

    def get_domain(self, domain: str): ...

    def create_domain(
        self,
        tenant_id: int,
        domain: str,
        *,
        created_by: int | None = None,
    ): ...

    def delete_domain(self, domain: str, *, tenant_id: int | None = None) -> None: ...


@runtime_checkable
class DomainVerificationPort(Protocol):
    def verify_domain(self, domain: str, *, tenant_id: int, actor_user_id: int | None = None): ...

    def challenge_for_domain(self, domain: str, *, tenant_id: int) -> tuple[str, str]: ...

    def cname_target(self) -> str: ...


__all__ = ["DomainRepositoryPort", "DomainVerificationPort"]
