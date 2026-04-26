# ORM modell: two_factor_codes tábla.
# 2026.03.07 - Sárközi Mihály

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import AuthBase


class TwoFactorCodeORM(AuthBase):
    __tablename__ = "two_factor_codes"
    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False) # User azonosító
    code_hash = Column(String(64), nullable=False)  # SHA-256 hex; nyers OTP nincs tárolva
    email = Column(String(255), nullable=False) # Email cím
    expires_at = Column(DateTime, nullable=False) # Kód lejárat dátuma
    used = Column(Boolean, default=False) # Kód használatának jelölése
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=False) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=False) # User azonosító
    __table_args__ = (
        Index("ix_2fa_user_expires", "user_id", "expires_at"),
        Index("ix_2fa_user_code_hash", "user_id", "code_hash"),
    )
