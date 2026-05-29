# backend/core/modules/users/domain/dto/user.py
# Feladat: A központi User domain DTO-t definiálja. Auth, permission, profil, tenant és audit mezőket hordoz, amelyeket core és app modulok szélesen használnak. Stabil platform identity contract.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

from core.kernel.runtime.clock import utc_now_naive

def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában."""
    return utc_now_naive()


@dataclass(frozen=True)
class User:
    id: Optional[int] # Bejegyzés Azonosító
    email: str # Email cím
    password_hash: str # Jelszó hash
    is_active: bool # Felhasználó statusza (aktív/inaktív)
    role: str  # "user" | "admin" | "owner" – owner = első regisztrált, nem törölhető, csak név/email (email kóddal)
    created_at: datetime # Készítés dátum és idő
    name: Optional[str] = None # Felhasználó név
    registration_completed_at: Optional[datetime] = None # Regisztrációs dátum és idő
    failed_login_attempts: int = 0 # Sikertelen belépések száma
    preferred_locale: Optional[str] = None  # hu | en | es, alapértelmezés: owneré
    preferred_theme: Optional[str] = None   # light | dark, alapértelmezés: owneré → light
    security_version: int = 0  # növeléskor minden régi token (user_ver) érvénytelen
    credentials_password_set: bool = True  # False: csak belső placeholder jelszó (meghívó / demo), még nincs saját jelszó
    pending_email: Optional[str] = None # Saját email cserekor megerősítésre váró új email cím
    pending_email_token_hash: Optional[str] = None # Saját email csere megerősítő token hash
    pending_email_expires_at: Optional[datetime] = None # Saját email csere token lejárata

    # Új, még nem persistált user példány létrehozása
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
            created_at=_utcnow_naive(),
            name=name,
            credentials_password_set=False,
        )

    # Owner szerepkörének ellenőrzése
    @property
    def is_owner(self) -> bool:
        """Az owner szerepkörének ellenőrzése."""
        return self.role == "owner"

    # DB-ben elmentett user állapot reprezentálása
    def persisted(self, *, id: int, created_at: datetime) -> "User":
        """DB-ben elmentett user állapot reprezentálása."""
        return replace(self, id=id, created_at=created_at)

    # User frissítése új értékekkel
    def with_updates(self, **kwargs) -> "User":
        """User frissítése új értékekkel."""
        return replace(self, **kwargs)
