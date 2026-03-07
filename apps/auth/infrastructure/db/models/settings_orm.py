# apps/auth/infrastructure/db/models/settings_orm.py
# ORM modell: settings tábla.
# 2026.03.07 - Sárközi Mihály

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

from apps.auth.infrastructure.db.models.base import AuthBase


class SettingsORM(AuthBase):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), server_default=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
