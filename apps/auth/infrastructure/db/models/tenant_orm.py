# apps/auth/infrastructure/db/models/tenant_orm.py
# ORM: tenants – subdomain slug (acme.teappod.hu → acme), egy tenant = egy cég.
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, DateTime

from apps.auth.infrastructure.db.models.base import PublicBase


class TenantORM(PublicBase):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, index=True, nullable=False)  # pl. acme
    name = Column(String(255), nullable=False)  # megjelenített név
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    security_version = Column(Integer, default=0, nullable=False)  # növeléskor minden régi token (tenant_ver) bukik
    is_active = Column(Boolean, default=True, nullable=False)  # tenant status cache forásként
