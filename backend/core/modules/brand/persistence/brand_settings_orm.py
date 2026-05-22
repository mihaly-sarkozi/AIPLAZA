# backend/core/modules/brand/persistence/brand_settings_orm.py
# Feladat: A tenant sémában tárolt brand_settings ORM modellje. Perzisztencia
# réteg, ezért SQLAlchemy import csak innen és repository/tenant hook adapterekből
# indulhat, domain/service importból nem.

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from core.kernel.db.model_bases import AuthBase


class BrandSettingsORM(AuthBase):
    __tablename__ = "brand_settings"

    id = Column(Integer, primary_key=True)
    display_name = Column(String(150), nullable=False, default="")
    logo_url = Column(String(500), nullable=False, default="")
    primary_color = Column(String(32), nullable=False, default="#2563eb")
    support_email = Column(String(255), nullable=False, default="")
    public_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=func.now(), server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), server_default=func.now())
    updated_by = Column(Integer, nullable=True)


__all__ = ["BrandSettingsORM"]
