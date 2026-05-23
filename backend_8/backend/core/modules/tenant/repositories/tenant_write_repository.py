# backend/core/modules/tenant/repositories/tenant_write_repository.py
# Feladat: Tenant public adatok író repository adaptere. Tenant rekordot, configot és domain rekordokat hoz létre/frissít/töröl, majd tenant routing cache invalidációt végez. Tenant write-side adat-hozzáférési réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.cache import invalidate_domain2tenant_cache, invalidate_tenant_cache
from core.modules.tenant.dto import TenantConfig
from core.modules.tenant.models.tenant_config_orm import TenantConfigORM
from core.modules.tenant.models.tenant_domain_orm import TenantDomainORM
from core.modules.tenant.models.tenant_orm import TenantORM
from core.modules.tenant.repositories.tenant_repository_base import TenantRepositoryBase


class TenantWriteRepository(TenantRepositoryBase):
    @staticmethod
    def _invalidate_tenant_snapshot(slug: str | None) -> None:
        invalidate_tenant_cache(slug)

    @staticmethod
    def _invalidate_domain_mapping(domain: str | None) -> None:
        invalidate_domain2tenant_cache(domain)

    def create(
        self,
        slug: str,
        name: str,
        *,
        created_by: int | None = None,
        is_active: bool = True,
    ):
        with self._sf() as db:
            self._use_public_schema(db)
            row = TenantORM(
                slug=slug,
                name=name,
                created_by=created_by,
                updated_by=created_by,
                is_active=is_active,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            self._invalidate_tenant_snapshot(row.slug)
            return self._to_tenant(row)

    def create_config(
        self,
        tenant_id: int,
        *,
        slug: str,
        package: str = "free",
        feature_flags: dict | None = None,
        limits: dict | None = None,
        created_by: int | None = None,
    ):
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantConfigORM).filter(TenantConfigORM.tenant_id == tenant_id).first()
            if row is None:
                row = TenantConfigORM(
                    tenant_id=tenant_id,
                    package=package,
                    feature_flags=feature_flags or {},
                    limits=limits or {},
                    created_by=created_by,
                    updated_by=created_by,
                )
                db.add(row)
            else:
                row.package = package
                row.feature_flags = feature_flags or {}
                row.limits = limits or {}
                row.updated_by = created_by
            db.commit()
            db.refresh(row)
            self._invalidate_tenant_snapshot(slug)
            return TenantConfig(
                tenant_id=row.tenant_id,
                slug=slug,
                package=row.package or "free",
                feature_flags=dict(row.feature_flags or {}),
                limits=dict(row.limits or {}),
            )

    def delete_config(self, tenant_id: int, *, slug: str | None = None) -> None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantConfigORM).filter(TenantConfigORM.tenant_id == tenant_id).first()
            if row is None:
                return
            effective_slug = slug
            if not effective_slug:
                tenant_row = db.get(TenantORM, tenant_id)
                effective_slug = tenant_row.slug if tenant_row else None
            db.delete(row)
            db.commit()
            self._invalidate_tenant_snapshot(effective_slug)

    def create_domain(
        self,
        tenant_id: int,
        domain: str,
        *,
        verified_at=None,
        created_by: int | None = None,
    ):
        normalized_domain = self._normalize_domain(domain)
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantDomainORM).filter(TenantDomainORM.domain == normalized_domain).first()
            if row is None:
                row = TenantDomainORM(
                    tenant_id=tenant_id,
                    domain=normalized_domain,
                    verified_at=verified_at,
                    created_by=created_by,
                    updated_by=created_by,
                )
                db.add(row)
                previous_domain = None
            else:
                previous_domain = row.domain
                row.tenant_id = tenant_id
                if verified_at is not None:
                    row.verified_at = verified_at
                row.updated_by = created_by
            db.commit()
            db.refresh(row)
            self._invalidate_domain_mapping(row.domain)
            if previous_domain and previous_domain != row.domain:
                self._invalidate_domain_mapping(previous_domain)
            return self._to_domain(row)

    def delete_by_slug(self, slug: str) -> None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if row:
                domains = [
                    domain_row.domain
                    for domain_row in db.query(TenantDomainORM).filter(TenantDomainORM.tenant_id == row.id).all()
                ]
                db.delete(row)
                db.commit()
                self._invalidate_tenant_snapshot(slug)
                for domain in domains:
                    self._invalidate_domain_mapping(domain)

    def assign_actor(self, tenant_id: int, actor_user_id: int) -> None:
        self.set_actor(tenant_id, actor_user_id, updated_by=actor_user_id)

    def set_actor(
        self,
        tenant_id: int,
        actor_user_id: int | None,
        *,
        updated_by: int | None = None,
    ) -> None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.get(TenantORM, tenant_id)
            if row:
                row.created_by = actor_user_id
                row.updated_by = updated_by if updated_by is not None else actor_user_id
                db.commit()
                self._invalidate_tenant_snapshot(row.slug)

    def activate(self, tenant_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.get(TenantORM, tenant_id)
            if row:
                row.is_active = True
                row.updated_by = updated_by
                db.commit()
                self._invalidate_tenant_snapshot(row.slug)

    def deactivate(self, tenant_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.get(TenantORM, tenant_id)
            if row:
                row.is_active = False
                row.updated_by = updated_by
                db.commit()
                self._invalidate_tenant_snapshot(row.slug)

    def increment_security_version(self, tenant_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.get(TenantORM, tenant_id)
            if row:
                row.security_version = getattr(row, "security_version", 0) + 1
                row.updated_by = updated_by
                db.commit()
                self._invalidate_tenant_snapshot(row.slug)

    def verify_domain(
        self,
        domain: str,
        *,
        verified_at=None,
        updated_by: int | None = None,
    ):
        normalized_domain = self._normalize_domain(domain)
        with self._sf() as db:
            self._use_public_schema(db)
            row = db.query(TenantDomainORM).filter(TenantDomainORM.domain == normalized_domain).first()
            if not row:
                return None
            row.verified_at = verified_at
            row.updated_by = updated_by
            db.commit()
            db.refresh(row)
            self._invalidate_domain_mapping(row.domain)
            return self._to_domain(row)

    def delete_domain(self, domain: str, *, tenant_id: int | None = None) -> None:
        normalized_domain = self._normalize_domain(domain)
        with self._sf() as db:
            self._use_public_schema(db)
            query = db.query(TenantDomainORM).filter(TenantDomainORM.domain == normalized_domain)
            if tenant_id is not None:
                query = query.filter(TenantDomainORM.tenant_id == tenant_id)
            row = query.first()
            if row is None:
                return
            resolved_domain = row.domain
            db.delete(row)
            db.commit()
            self._invalidate_domain_mapping(resolved_domain)
