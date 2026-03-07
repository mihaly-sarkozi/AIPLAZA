# apps/auth/infrastructure/db/repositories/tenant_repository.py
# Tenants + tenant_configs + tenant_domains (public). Domain→tenant, status, config cache forrás.
# 2026.03.07 - Sárközi Mihály

from datetime import timezone
from sqlalchemy import text
from apps.auth.infrastructure.db.models import TenantORM, TenantConfigORM, TenantDomainORM
from apps.auth.ports.tenant_repository_interface import TenantRepositoryInterface
from apps.auth.domain.tenant import Tenant
from apps.auth.domain.tenant_status import TenantStatus
from apps.auth.domain.tenant_config import TenantConfig
from apps.auth.domain.tenant_domain import TenantDomain


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
                security_version=getattr(row, "security_version", 0),
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
                security_version=getattr(row, "security_version", 0),
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
                security_version=getattr(row, "security_version", 0),
            )

    def increment_security_version(self, tenant_id: int) -> None:
        """Tenant-oldali force revoke: policy/role változás után növeljük; minden régi token (tenant_ver) bukik."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.get(TenantORM, tenant_id)
            if row:
                row.security_version = getattr(row, "security_version", 0) + 1
                db.commit()

    def get_by_domain(self, domain: str) -> Tenant | None:
        """Egyedi domain (tenant_domains) → tenant. A domain normalizált (kisbetű)."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            link = db.query(TenantDomainORM).filter(TenantDomainORM.domain == domain).first()
            if not link:
                return None
            row = db.get(TenantORM, link.tenant_id)
            if not row:
                return None
            return Tenant(
                id=row.id,
                slug=row.slug,
                name=row.name,
                created_at=self._normalize_dt(row.created_at),
                security_version=getattr(row, "security_version", 0),
            )

    def get_tenant_status(self, slug: str) -> TenantStatus | None:
        """Tenant status (is_active) – status cache forrás."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not row:
                return None
            return TenantStatus(
                tenant_id=row.id,
                slug=row.slug,
                is_active=getattr(row, "is_active", True),
                suspended_reason=None,
            )

    def get_tenant_config(self, slug: str) -> TenantConfig | None:
        """Tenant config (package, feature_flags, limits) – config cache forrás."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            tenant = db.query(TenantORM).filter(TenantORM.slug == slug).first()
            if not tenant:
                return None
            row = db.query(TenantConfigORM).filter(TenantConfigORM.tenant_id == tenant.id).first()
            if not row:
                return TenantConfig(
                    tenant_id=tenant.id,
                    slug=slug,
                    package="free",
                    feature_flags={},
                    limits={},
                )
            return TenantConfig(
                tenant_id=row.tenant_id,
                slug=slug,
                package=row.package or "free",
                feature_flags=dict(row.feature_flags or {}),
                limits=dict(row.limits or {}),
            )

    def list_domains_for_tenant(self, tenant_id: int) -> list[TenantDomain]:
        """Nyilvános nyilvántartás: mely domainek tartoznak a tenanthoz."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            rows = db.query(TenantDomainORM).filter(TenantDomainORM.tenant_id == tenant_id).all()
            return [
                TenantDomain(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    domain=r.domain,
                    verified_at=self._normalize_dt(r.verified_at) if r.verified_at else None,
                    created_at=self._normalize_dt(r.created_at) if r.created_at else None,
                )
                for r in rows
            ]
