# backend/core/kernel/domain/runtime.py
# Feladat: A kernel domain runtime-facing exportfelülete. DTO-kat, policyt, repositoryt, service-t, routert és service dependency helper aliasokat ad tovább egy helyről. Kernel domain integrációs façade, amely egyszerűsíti a külső importokat.
# Sárközi Mihály - 2026.05.21

from core.kernel.domain.dto import (
    DomainCreateRequest,
    DomainOverviewResponse,
    DomainRecordResponse,
    DomainVerifyRequest,
)
from core.kernel.domain.policies import DomainPolicy
from core.kernel.domain.repositories import DomainRepository
from core.kernel.domain.router import get_domain_service, router
from core.kernel.domain.services import DomainService

__all__ = [
    "DomainCreateRequest",
    "DomainOverviewResponse",
    "DomainPolicy",
    "DomainRecordResponse",
    "DomainRepository",
    "DomainService",
    "DomainVerifyRequest",
    "get_domain_service",
    "router",
]
