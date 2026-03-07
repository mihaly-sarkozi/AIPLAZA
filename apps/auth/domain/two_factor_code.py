# apps/auth/domain/two_factor_code.py
# 2FA kód domain modell
# 2026.03.07 - Sárközi Mihály

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TwoFactorCode:
    id: Optional[int]
    user_id: int
    code: str
    email: str
    expires_at: datetime
    used: bool
    created_at: datetime
    
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
            created_at=datetime.utcnow()
        )
    
    def persisted(self, *, id: int, created_at: datetime) -> "TwoFactorCode":
        """DB-ben elmentett kód állapot reprezentálása."""
        from dataclasses import replace
        return replace(self, id=id, created_at=created_at)
    
    def mark_as_used(self) -> "TwoFactorCode":
        """Kód használatának jelölése."""
        from dataclasses import replace
        return replace(self, used=True)
    
    def is_expired(self) -> bool:
        """Ellenőrzi, hogy lejárt-e a kód."""
        return datetime.utcnow() > self.expires_at

