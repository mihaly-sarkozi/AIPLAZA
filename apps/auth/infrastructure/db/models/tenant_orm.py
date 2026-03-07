# apps/auth/infrastructure/db/models/tenant_orm.py
# ORM: tenants – subdomain slug (acme.teappod.hu → acme), egy tenant = egy cég.
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime

from apps.auth.infrastructure.db.models.base import PublicBase


class TenantORM(PublicBase):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, index=True, nullable=False)  # pl. acme
    name = Column(String(255), nullable=False)  # megjelenített név
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
