# Ez a fájl az adatátadási objektumokat és a külső interfészhez tartozó struktúrákat tartalmazza.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TenantDomainInfo:
    request_host: str | None
    resolved_host: str | None
    is_custom_domain: bool
    verified_at: datetime | None = None
