# apps/users/domain/user.py
# Felhasználó domain modell (auth és users modul is használja).
# 2026.03.07 - Sárközi Mihály

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class User:
    id: Optional[int]
    email: str
    password_hash: str
    is_active: bool
    role: str  # "user" | "admin" | "owner" – owner = első regisztrált, nem törölhető, csak név/email (email kóddal)
    created_at: datetime
    name: Optional[str] = None
    registration_completed_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    preferred_locale: Optional[str] = None  # hu | en | es, alapértelmezés: owneré
    preferred_theme: Optional[str] = None   # light | dark, alapértelmezés: owneré → light
    security_version: int = 0  # növeléskor minden régi token (user_ver) érvénytelen

    @classmethod
    def new(
        cls,
        email: str,
        password_hash: str,
        role: str = "user",
        is_active: bool = True,
        name: Optional[str] = None,
    ) -> "User":
        """Új, még nem persistált user példány létrehozása. Meghívásnál is_active=False (regisztráció alatt)."""
        return cls(
            id=None,
            email=email,
            password_hash=password_hash,
            is_active=is_active,
            role=role,
            created_at=datetime.utcnow(),
            name=name,
        )

    @property
    def is_owner(self) -> bool:
        """Az owner szerepkörének ellenőrzése."""
        return self.role == "owner"

    def persisted(self, *, id: int, created_at: datetime) -> "User":
        """DB-ben elmentett user állapot reprezentálása."""
        return replace(self, id=id, created_at=created_at)

    def with_updates(self, **kwargs) -> "User":
        """User frissítése új értékekkel."""
        return replace(self, **kwargs)
