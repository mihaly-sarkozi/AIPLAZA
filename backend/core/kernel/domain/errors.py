# backend/core/kernel/domain/errors.py
# Feladat: A custom domain service typed exception készletét definiálja. Tenant hiány, foglalt domain, nem található domain, lifecycle tiltás, DNS verification hiba és primary domain törlési tiltás külön hibaként jelenik meg, hogy a router tisztán mapelje HTTP státuszokra. Kernel domain error contract réteg.
# Sárközi Mihály - 2026.05.21

"""Domain service hibatípusok.

A DomainService typed exception-öket dob, a route handler ezeket kapja el
és mapeli HTTP státuszkódra - string-alapú ValueError ellenőrzések helyett.
"""
from __future__ import annotations


class DomainServiceError(Exception):
    """Alap domain-service hiba."""


class TenantNotFoundError(DomainServiceError):
    """A tenant slug alapján nem található."""


class DomainTakenError(DomainServiceError):
    """A domain már más tenanthez tartozik."""


class DomainNotFoundError(DomainServiceError):
    """A keresett domain nem található a tenanthez."""


class DomainManagementBlockedError(DomainServiceError):
    """A tenant állapota miatt a domain-kezelés tiltott."""

    def __init__(self, status: str | None = None) -> None:
        super().__init__(f"tenant_domain_management_blocked:{status or 'unknown'}")
        self.status = status


class DomainDnsVerificationFailedError(DomainServiceError):
    """A domain DNS ellenőrzés sikertelen."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"domain_dns_verification_failed:{reason}")
        self.reason = reason


class DomainPrimaryDeleteBlockedError(DomainServiceError):
    """Elsődleges platform domain törlése tiltott."""
