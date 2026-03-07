# apps/auth/infrastructure/db/models/tenant_domain_orm.py
# ORM: tenant_domains (public) – domain → tenant nyilvántartás; regisztráció/ellenőrzés.
# 2026.03 – Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint

from apps.auth.infrastructure.db.models.base import PublicBase


class TenantDomainORM(PublicBase):
    __tablename__ = "tenant_domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_tenant_domains_domain"), {"schema": "public"})
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)  # normalizált host (kisbetű, port nélkül)
    verified_at = Column(DateTime(timezone=True), nullable=True)  # None = még nincs ellenőrizve (pl. DNS)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
