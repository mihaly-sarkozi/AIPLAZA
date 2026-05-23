# backend/core/modules/auth/domain/dto/two_factor_code.py
# Feladat: 2FA email kód domain DTO-t definiál. Userhez, emailhez, lejárathoz, felhasználtsághoz és létrehozási időhöz kapcsolódó állapotot hordoz, immutable helper metódusokkal új kód, persisted állapot, used jelölés és lejárat ellenőrzéséhez. Auth domain DTO a 2FA service és repository között.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

from core.kernel.runtime.clock import utc_now_naive

def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában."""
    return utc_now_naive()


@dataclass(frozen=True)
class TwoFactorCode:
    id: Optional[int] # Bejegyzés Azonosító
    user_id: int # User azonosító
    code: str # 2FA kód
    email: str # Email cím
    expires_at: datetime # Kód lejárat dátuma
    used: bool # Kód használatának jelölése
    created_at: datetime # Készítés dátum és idő

    # Új 2FA kód létrehozása
    @classmethod
    def new(cls, user_id: int, code: str, email: str, expires_at: datetime) -> "TwoFactorCode":
        """Új 2FA kód létrehozása."""
        return cls(
            id=None,
            user_id=user_id,
            code=code,
            email=email,
            expires_at=expires_at,
            used=False,
            created_at=_utcnow_naive(),
        )


    # DB-ben elmentett kód állapot reprezentálása
    def persisted(self, *, id: int, created_at: datetime) -> "TwoFactorCode":
        """DB-ben elmentett kód állapot reprezentálása."""
        return replace(self, id=id, created_at=created_at)


    # Kód használatának jelölése
    def mark_as_used(self) -> "TwoFactorCode":
        """Kód használatának jelölése."""
        return replace(self, used=True)


    # Kód lejártának ellenőrzése
    def is_expired(self) -> bool:
        """Ellenőrzi, hogy lejárt-e a kód."""
        return _utcnow_naive() > self.expires_at
