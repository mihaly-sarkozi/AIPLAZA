# apps/auth/domain/session.py
"""
A bejelentkezési session reprezentálja és
kezeli a token logikát
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

@dataclass(frozen=True)
class Session:
    id: Optional[int]
    user_id: int
    jti: str
    token_hash: str
    valid: bool = True
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    expires_at: datetime = None
    created_at: Optional[datetime] = None

    @classmethod
    def new(
        cls,
        *,
        user_id: int,
        jti: str,
        token_hash: str,
        expires_at: datetime,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> "Session":
        return cls(
            id=None,
            user_id=user_id,
            jti=jti,
            token_hash=token_hash,
            valid=True,
            ip=ip,
            user_agent=user_agent,
            expires_at=expires_at,
            created_at=None,
        )

    def persisted(self, *, id: int, created_at: datetime) -> "Session":
        """DB-ből visszakapott állapot reprezentálása."""
        return replace(self, id=id, created_at=created_at)

    # --- Domain műveletek ---

    def invalidate(self) -> "Session":
        """Session visszavonása logout / rotation esetén."""
        return replace(self, valid=False)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Ellenőrzi, hogy a session lejárt-e."""
        if not self.expires_at:
            return True

        # belső now kezelése
        if now is None:
            now = datetime.now(timezone.utc)

        exp = self.expires_at

        # timezone-naive biztonságos kezelése
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        return now >= exp

    def refresh(self, *, new_expires_at: datetime) -> "Session":
        """Új lejárati idővel rendelkező példány."""
        return replace(self, expires_at=new_expires_at, valid=True)
