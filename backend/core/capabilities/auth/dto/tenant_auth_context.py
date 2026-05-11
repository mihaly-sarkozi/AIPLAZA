# Ez a fájl az adatátadási objektumokat és a külső interfészhez tartozó struktúrákat tartalmazza.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantAuthContext:
    tenant_id: int | None
    slug: str | None
    correlation_id: str | None
    security_version: int
    trial_active: bool = False
