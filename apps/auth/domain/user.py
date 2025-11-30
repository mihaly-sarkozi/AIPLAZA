# apps/auth/domain/user.py
"""
A felhasználó domain modellje.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class User:
    id: Optional[int]
    email: str
    password_hash: str
    is_active: bool
    role: str
    is_superuser: bool
    created_at: datetime

    @classmethod
    def new(cls, email: str, password_hash: str, role: str = "user", is_superuser: bool = False) -> "User":
        """Új, még nem persistált user példány létrehozása."""
        return cls(
            id=None,
            email=email,
            password_hash=password_hash,
            is_active=True,
            role=role,
            is_superuser=is_superuser,
            created_at=datetime.utcnow(),  # vagy datetime.now(timezone.utc)
        )

    def persisted(self, *, id: int, created_at: datetime) -> "User":
        """DB-ben elmentett user állapot reprezentálása."""
        return replace(self, id=id, created_at=created_at)
    
    def with_updates(self, **kwargs) -> "User":
        """User frissítése új értékekkel."""
        return replace(self, **kwargs)
