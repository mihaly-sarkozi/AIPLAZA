# backend/core/modules/tenant/models/tenant_domain_orm.py
# Feladat: A public schema tenant domain táblájának SQLAlchemy modellje. Primary és custom domainek, verification állapot és audit mezők tárolására szolgál. Tenant domain perzisztencia modell.
# Sárközi Mihály - 2026.05.21

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint

from core.kernel.runtime.clock import utc_now
from core.kernel.db.model_bases import PublicBase


class TenantDomainORM(PublicBase):
    __tablename__ = "tenant_domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_tenant_domains_domain"), {"schema": "public"})
    id = Column(Integer, primary_key=True) # Bejegyzés Azonosító
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True) # Tenant azonosító
    domain = Column(String(255), nullable=False, index=True)  # Normalizált host (kisbetű, port nélkül)
    verified_at = Column(DateTime(timezone=True), nullable=True)  # Ellenprzés dátuma? None = még nincs ellenőrizve (pl. DNS)
    created_at = Column(DateTime(timezone=True), default=utc_now) # Készítés dátum és idő
    created_by = Column(Integer, nullable=True) # User azonosító
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now) # Frissítés dátum és idő
    updated_by = Column(Integer, nullable=True) # User azonosító
