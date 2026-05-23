# backend/core/modules/tenant/models/tenant_orm.py
# Feladat: A public schema tenants táblájának SQLAlchemy modellje. Tenant alapadatokat, státuszt, slugot, schema nevet és lifecycle mezőket tárol. Tenant public perzisztencia modell.
# Sárközi Mihály - 2026.05.21

from sqlalchemy import Boolean, Column, Integer, String, DateTime

from core.kernel.runtime.clock import utc_now
from core.kernel.db.model_bases import PublicBase


class TenantORM(PublicBase):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    slug = Column(String(64), unique=True, index=True, nullable=False)  # subdomain slug: pl. "demo" → "demo.domain.hu"
    name = Column(String(255), nullable=False)  # megjelenített név
    created_at = Column(DateTime, default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=True) # User azonosító
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=True) # User azonosító
    security_version = Column(Integer, default=0, nullable=False)  # növeléskor minden régi token (tenant_ver) bukik
    is_active = Column(Boolean, default=True, nullable=False)  # tenant domain ellenőrzése sikeres volt-e
