# ORM: 2FA sikertelen próbálkozások (brute-force védelem: token / user / IP alapú limit).
# 2026.03 - Sárközi Mihály

from sqlalchemy import Column, Integer, String, DateTime, Index

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import AuthBase


class TwoFactorAttemptORM(AuthBase):
    __tablename__ = "two_factor_attempts"
    id = Column(Integer, primary_key=True, autoincrement=True) # Bejegyzés Azonosító
    scope = Column(String(20), nullable=False)  # 'token' | 'user' | 'ip'
    scope_key = Column(String(128), nullable=False) # Scope kulcs
    attempts = Column(Integer, nullable=False, default=0) # Próbálkozások száma
    window_start_at = Column(DateTime, nullable=False) # Ablak kezdete
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=False) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=False) # User azonosító
    __table_args__ = (
        Index("ix_2fa_attempt_scope_key", "scope", "scope_key", unique=True),
    )
