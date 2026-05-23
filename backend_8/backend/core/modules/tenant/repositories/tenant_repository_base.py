# backend/core/modules/tenant/repositories/tenant_repository_base.py
# Feladat: A tenant repositoryk közös alapját tartalmazza. Session factoryt, sort DTO-vá alakító helper logikát és közös query segédeket ad az olvasó/író repositoryknak. Tenant repository shared adapter réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from sqlalchemy import text

from shared.utils import normalize_utc_datetime

from core.modules.tenant.dto import (
    Tenant,
    TenantConfig,
    TenantDomain,
    TenantSnapshot,
    TenantStatus,
)
from core.modules.tenant.models.tenant_config_orm import TenantConfigORM
from core.modules.tenant.models.tenant_domain_orm import TenantDomainORM
from core.modules.tenant.models.tenant_orm import TenantORM


class TenantRepositoryBase:
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _use_public_schema(db) -> None:
        get_bind = getattr(db, "get_bind", None)
        bind = get_bind() if callable(get_bind) else None
        if bind is not None and bind.dialect.name == "sqlite":
            return
        db.execute(text("SET search_path TO public"))

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        return (domain or "").strip().lower()

    @staticmethod
    def _to_tenant(row: TenantORM) -> Tenant:
        return Tenant(
            id=row.id,
            slug=row.slug,
            name=row.name,
            created_at=normalize_utc_datetime(row.created_at),
            security_version=getattr(row, "security_version", 0),
        )

    @staticmethod
    def _to_status(row: TenantORM) -> TenantStatus:
        return TenantStatus(
            tenant_id=row.id,
            slug=row.slug,
            is_active=getattr(row, "is_active", True),
            suspended_reason=None,
        )

    @staticmethod
    def _to_config(row: TenantORM, config_row: TenantConfigORM | None) -> TenantConfig:
        if config_row is None:
            return TenantConfig(
                tenant_id=row.id,
                slug=row.slug,
                package="free",
                feature_flags={},
                limits={},
            )
        return TenantConfig(
            tenant_id=config_row.tenant_id,
            slug=row.slug,
            package=config_row.package or "free",
            feature_flags=dict(config_row.feature_flags or {}),
            limits=dict(config_row.limits or {}),
        )

    def _get_config_row(self, db, tenant_id: int) -> TenantConfigORM | None:
        return db.query(TenantConfigORM).filter(TenantConfigORM.tenant_id == tenant_id).first()

    def _build_snapshot(self, row: TenantORM, config_row: TenantConfigORM | None) -> TenantSnapshot:
        return TenantSnapshot(
            tenant_id=row.id,
            slug=row.slug,
            name=row.name,
            created_at=normalize_utc_datetime(row.created_at),
            security_version=getattr(row, "security_version", 0),
            status=self._to_status(row),
            config=self._to_config(row, config_row),
        )

    @staticmethod
    def _to_domain(row: TenantDomainORM) -> TenantDomain:
        return TenantDomain(
            id=row.id,
            tenant_id=row.tenant_id,
            domain=row.domain,
            verified_at=normalize_utc_datetime(row.verified_at) if row.verified_at else None,
            created_at=normalize_utc_datetime(row.created_at) if row.created_at else None,
        )
