# apps/auth/domain/tenant.py
# Tenant domain modell, a különböző cégeket reprezentálja
# 2026.03.07 - Sárközi Mihály

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Tenant:
    id: Optional[int]
    slug: str
    name: str
    created_at: datetime
