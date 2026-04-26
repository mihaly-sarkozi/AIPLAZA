# Felhasználó adatok tábla leképzése.
# 2026.04.03 - Sárközi Mihály

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import TenantSchemaBase


class UserORM(TenantSchemaBase):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    email = Column(String(255), nullable=False, unique=True, index=True) # Email cím
    name = Column(String(255), nullable=True) # Felhasználó név
    password_hash = Column(String(255), nullable=False) # Jelszó hash
    is_active = Column(Boolean, default=True) # Felhasználó statusza (aktív/inaktív)
    role = Column(String(20), nullable=False, server_default="user") # Felhasználó szerepköre (user/admin/owner)
    created_at = Column(DateTime, default=utc_now)   # készítés dátum és idő
    created_by = Column(Integer, nullable=True) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # frissítés dátum és idő
    updated_by = Column(Integer, nullable=True) # User azonosító
    deleted_at = Column(DateTime(timezone=True), nullable=True) # Törölés dátum
    deleted_by = Column(Integer, nullable=True) # User azonosító
    registration_completed_at = Column(DateTime(timezone=True), nullable=True) # Regisztrációs dátum
    failed_login_attempts = Column(Integer, default=0, nullable=False) # Sikertelen belépések száma
    preferred_locale = Column(String(10), nullable=True) # Preferált nyelv (hu/en/es)
    preferred_theme = Column(String(10), nullable=True) # Preferált téma (light/dark)
    security_version = Column(Integer, default=0, nullable=False) # Biztonsági verzió (növeléskor minden régi token érvénytelen)
    credentials_password_set = Column(Boolean, default=True, nullable=False, server_default="true")  # saját jelszó beállítva

    __table_args__ = (Index("ix_users_created_at", "created_at"),)
