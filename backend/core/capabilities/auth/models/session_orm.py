# ORM modell: refresh_tokens tábla.
# 2026.03.07 - Sárközi Mihály

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import AuthBase


class SessionORM(AuthBase):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False) # User azonosító
    jti = Column(String(128), unique=True, index=True, nullable=False) # JTI
    token_hash = Column(String(255), nullable=False) # Token hash
    ip = Column(String(64)) # IP cím
    user_agent = Column(String(255)) # User agent
    valid = Column(Boolean, default=True) # Valid jelölése
    expires_at = Column(DateTime, nullable=False) # Token lejárat dátuma
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=False) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=False) # User azonosító
    __table_args__ = (
        Index("ix_refresh_user_valid", "user_id", "valid"),
        Index("ix_refresh_token_hash", "token_hash"),  # logout invalidate_by_hash
    )
