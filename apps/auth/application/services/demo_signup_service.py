# apps/auth/application/services/demo_signup_service.py
# Demo/install regisztráció: tenant + séma + első user (meghívás, set-password email).
# Nyilvános flow: nincs tenant context; létrehozzuk a tenánt, sémát, usert (invite), link a tenant hostra.
# 2026.02 - Sárközi Mihály

from __future__ import annotations

import re
from typing import Optional

from config.settings import settings
from sqlalchemy import create_engine

from apps.auth.infrastructure.db.tenant_schema import create_tenant_schema
from apps.auth.ports.tenant_repository_interface import TenantRepositoryInterface
from apps.core.db.tenant_context import current_tenant_schema


def normalize_slug(name: str) -> str:
    """Tudástár névből → slug (pl. 'Acme Kft' → 'acme-kft'). Ország kód egyenlőre nincs."""
    safe = re.sub(r"[^a-zA-Z0-9\s\-]", "", (name or "").strip())
    safe = re.sub(r"\s+", "-", safe).strip("-").lower()[:64]
    return safe


def slug_is_valid(slug: str) -> bool:
    """Tenant slug formátum (alphanumeric + underscore)."""
    return bool(slug and re.match(r"^[a-z0-9][a-z0-9_-]*$", slug) and len(slug) <= 64)


class DemoSignupService:
    def __init__(
        self,
        tenant_repository: TenantRepositoryInterface,
        user_service,  # UserService – create() hívás tenant context alatt
        request_base_url_builder,  # callable(slug) -> str
    ):
        self.tenant_repo = tenant_repository
        self.user_service = user_service
        self.request_base_url_builder = request_base_url_builder

    def is_slug_available(self, slug: str) -> bool:
        if not slug_is_valid(slug):
            return False
        return self.tenant_repo.get_by_slug(slug) is None

    def signup(
        self,
        *,
        email: str,
        kb_name: str,
        name: str,
        company_name: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> str:
        """
        Tenant + séma + első user (invite) létrehozása. Vissza: slug.
        current_tenant_schema-t ideiglenesen beállítjuk, hogy a user a megfelelő sémában jöjjön létre.
        """
        slug = normalize_slug(kb_name)
        if not slug_is_valid(slug):
            raise ValueError("invalid_slug")
        if self.tenant_repo.get_by_slug(slug) is not None:
            raise ValueError("slug_taken")

        tenant_name = (company_name or kb_name or slug).strip() or slug
        tenant = self.tenant_repo.create(slug, tenant_name)

        engine = create_engine(settings.database_url, future=True)
        create_tenant_schema(engine, slug)
        engine.dispose()

        base_url = self.request_base_url_builder(slug)
        token = current_tenant_schema.set(slug)
        try:
            self.user_service.create(
                email=email.strip(),
                name=(name or "").strip() or None,
                role="owner",
                request_base_url=base_url,
            )
        finally:
            current_tenant_schema.reset(token)

        return slug
