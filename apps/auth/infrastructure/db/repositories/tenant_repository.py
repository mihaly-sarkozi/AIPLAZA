# apps/auth/infrastructure/db/repositories/tenant_repository.py
# Tenants tábla mindig public sémában van – minden hívás előtt search_path = public.
# 2026.03.07 - Sárközi Mihály

from datetime import timezone
from sqlalchemy import text
from apps.auth.infrastructure.db.models import TenantORM
from apps.auth.ports.tenant_repository_interface import TenantRepositoryInterface
from apps.auth.domain.tenant import Tenant


class TenantRepository(TenantRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def get_by_slug(self, slug: str) -> Tenant | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not row:
                return None
            return Tenant(
                id=row.id,
                slug=row.slug,
                name=row.name,
                created_at=self._normalize_dt(row.created_at),
            )

    def get_by_id(self, tenant_id: int) -> Tenant | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.get(TenantORM, tenant_id)
            if not row:
                return None
            return Tenant(
                id=row.id,
                slug=row.slug,
                name=row.name,
                created_at=self._normalize_dt(row.created_at),
            )

    def create(self, slug: str, name: str) -> Tenant:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = TenantORM(slug=slug, name=name)
            db.add(row)
            db.commit()
            db.refresh(row)
            return Tenant(
                id=row.id,
                slug=row.slug,
                name=row.name,
                created_at=self._normalize_dt(row.created_at),
            )
