# backend/core/modules/settings/models/settings_orm.py
# Feladat: A tenant schema settings táblájának SQLAlchemy modellje.

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, func

from core.kernel.db.model_bases import AuthBase


class SettingsORM(AuthBase):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=func.now(), server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), server_default=func.now())
    updated_by = Column(Integer, nullable=True)


__all__ = ["SettingsORM"]
