# backend/core/modules/tenant/models/tenant_config_orm.py
# Feladat: A public schema tenant config táblájának SQLAlchemy modellje. Tenanthez tartozó konfigurációs mezőket és demo/provisioning állapotokat tárol. Tenant konfigurációs perzisztencia modell.
# Sárközi Mihály - 2026.05.21

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.kernel.runtime.clock import utc_now
from core.kernel.db.model_bases import PublicBase


class TenantConfigORM(PublicBase):
    __tablename__ = "tenant_configs"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), unique=True, nullable=False) # Tenant azonosító
    package = Column(String(64), nullable=False, default="free")  # Tenant csomag (free/pro/enterprise)
    feature_flags = Column(JSONB, nullable=False, default=dict)  # Feature flag-ek (JSON-szerű)
    limits = Column(JSONB, nullable=False, default=dict)  # {"max_users": 10, "storage_mb": 1024}
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=True) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=True) # User azonosító

    tenant = relationship("TenantORM", backref="config", uselist=False)
