# ORM: pending_2fa_logins – 2FA 1. lépés után ide kerül a token (2. lépésben consume).
# 2026.03.07 - Sárközi Mihály

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import AuthBase


class Pending2FAORM(AuthBase):
    __tablename__ = "pending_2fa_logins"
    id = Column(Integer, primary_key=True)  # Bejegyzés Azonosító
    token = Column(String(64), unique=True, index=True, nullable=False) # Pending token
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True) # User azonosító
    expires_at = Column(DateTime, nullable=False) # Kód lejárat dátuma
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=False) # User azonosító
