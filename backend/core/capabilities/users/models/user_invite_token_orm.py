# Meghívó token tábla leképzése.
# 2026.04.03 - Sárközi Mihály

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import TenantSchemaBase


class UserInviteTokenORM(TenantSchemaBase):
    __tablename__ = "user_invite_tokens"

    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True) # Mehívott user azonosító 
    token_hash = Column(String(255), nullable=False, unique=True, index=True) # Token hash az azonosításhoz
    expires_at = Column(DateTime(timezone=True), nullable=False) # Token lejárat dátuma
    used_at = Column(DateTime(timezone=True), nullable=True) # Felhasználás dátuma
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=True) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=True) # User azonosító
