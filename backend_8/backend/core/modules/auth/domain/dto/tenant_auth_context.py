# backend/core/modules/auth/domain/dto/tenant_auth_context.py
# Feladat: Az auth use case-ekhez szükséges minimális tenant kontextus DTO-t definiálja. Tenant azonosítót, slugot, correlation ID-t, tenant security versiont és trial állapotot hordoz a token kiadás és validáció támogatására. Auth domain DTO a HTTP tenant context és use case réteg között.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantAuthContext:
    tenant_id: int | None
    slug: str | None
    correlation_id: str | None
    security_version: int
    trial_active: bool = False
