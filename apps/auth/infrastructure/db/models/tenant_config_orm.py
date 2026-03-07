# apps/auth/infrastructure/db/models/tenant_config_orm.py
# ORM: tenant_configs (public) – csomag, feature_flags, limits; cache-elhető.
# 2026.03 – Sárközi Mihály

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from apps.auth.infrastructure.db.models.base import PublicBase


class TenantConfigORM(PublicBase):
    __tablename__ = "tenant_configs"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    package = Column(String(64), nullable=False, default="free")  # free, pro, enterprise
    feature_flags = Column(JSONB, nullable=False, default=dict)  # {"sso": true, "api_export": false}
    limits = Column(JSONB, nullable=False, default=dict)  # {"max_users": 10, "storage_mb": 1024}

    tenant = relationship("TenantORM", backref="config", uselist=False)
