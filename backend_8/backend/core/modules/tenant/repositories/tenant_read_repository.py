# backend/core/modules/tenant/repositories/tenant_read_repository.py
# Feladat: Tenant public adatok olvasó repository adaptere. Slug, domain és azonosító alapján tenant snapshotokat, configot és domain listákat olvas. Tenant read-side adat-hozzáférési réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.dto import TenantConfig
from core.modules.tenant.models.tenant_config_orm import TenantConfigORM
from core.modules.tenant.models.tenant_domain_orm import TenantDomainORM
from core.modules.tenant.models.tenant_orm import TenantORM
from core.modules.tenant.repositories.tenant_repository_base import TenantRepositoryBase


class TenantReadRepository(TenantRepositoryBase):
    def get_by_slug(self, slug: str):
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not row:
                return None
            return self._to_tenant(row)

    def get_by_id(self, tenant_id: int):
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.get(TenantORM, tenant_id)
            if not row:
                return None
            return self._to_tenant(row)

    def get_snapshot_by_slug(self, slug: str):
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not row:
                return None
            return self._build_snapshot(row, self._get_config_row(db, row.id))

    def get_snapshot_by_domain(self, domain: str):
        normalized_domain = self._normalize_domain(domain)
        with self._sf() as db:
            self._use_public_schema(db)
            link = (
                db.query(TenantDomainORM)
                .filter(
                    TenantDomainORM.domain == normalized_domain,
                    TenantDomainORM.verified_at.isnot(None),
                )
                .first()
            )
            if not link:
                return None
            row = db.get(TenantORM, link.tenant_id)
            if not row:
                return None
            return self._build_snapshot(row, self._get_config_row(db, row.id))

    def get_config_by_tenant_id(self, tenant_id: int, *, slug: str | None = None):
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantConfigORM).filter(TenantConfigORM.tenant_id == tenant_id).first()
            if row is None:
                return None
            effective_slug = slug
            if not effective_slug:
                tenant_row = db.get(TenantORM, tenant_id)
                effective_slug = tenant_row.slug if tenant_row else ""
            return TenantConfig(
                tenant_id=row.tenant_id,
                slug=effective_slug or "",
                package=row.package or "free",
                feature_flags=dict(row.feature_flags or {}),
                limits=dict(row.limits or {}),
            )

    def get_domain(self, domain: str):
        normalized_domain = self._normalize_domain(domain)
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantDomainORM).filter(TenantDomainORM.domain == normalized_domain).first()
            if not row:
                return None
            return self._to_domain(row)

    def get_actor_user_id(self, tenant_id: int) -> int | None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.get(TenantORM, tenant_id)
            if not row:
                return None
            return getattr(row, "created_by", None)

    def get_by_domain(self, domain: str):
        normalized_domain = self._normalize_domain(domain)
        with self._sf() as db:
            self._use_public_schema(db)
            link = (
                db.query(TenantDomainORM)
                .filter(
                    TenantDomainORM.domain == normalized_domain,
                    TenantDomainORM.verified_at.isnot(None),
                )
                .first()
            )
            if not link:
                return None
            row = db.get(TenantORM, link.tenant_id)
            if not row:
                return None
            return self._to_tenant(row)

    def get_tenant_status(self, slug: str):
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not row:
                return None
            return self._to_status(row)

    def get_tenant_config(self, slug: str):
        with self._sf() as db:
            self._use_public_schema(db)
            tenant = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not tenant:
                return None
            row = self._get_config_row(db, tenant.id)
            return self._to_config(tenant, row)

    def list_domains_for_tenant(self, tenant_id: int):
        with self._sf() as db:
            self._use_public_schema(db)
            rows = db.query(TenantDomainORM).filter(TenantDomainORM.tenant_id == tenant_id).all()
            return [self._to_domain(row) for row in rows]
