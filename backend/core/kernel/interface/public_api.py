# backend/core/kernel/interface/public_api.py
# Feladat: Géppel ellenőrizhető publikus import boundary listákat tartalmaz. Az architektúra tesztek ebből döntik el, hogy app modulok milyen core és shared felületeket importálhatnak. Core governance interface, amely a modularitási szabályokat kódban rögzíti.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

"""Machine-readable app platform import boundaries."""

PUBLIC_CORE_API_PREFIXES: tuple[str, ...] = (
    # Stable platform interfaces
    "core.kernel.interface",
    "core.modules.tenant.extensions.tenant_hooks",
    "core.modules.settings.models.settings_orm",
    "core.modules.settings.registry.settings_section_registry",
    "core.modules.settings.repository.settings_repository",
    "core.modules.settings.service.settings_service",
    "core.modules.settings.tenant_hooks",
    "core.modules.auth.web.dependencies.auth_dependencies",
    # Shared capability interfaces used by apps
    "core.modules.users.domain.dto",
    "core.modules.users.models.user_orm",
    "core.modules.users.repository.persistence.user_repository",
    # Tenant integration surfaces
    "core.modules.tenant.context",
    "core.modules.tenant.models.tenant_orm",
    "core.modules.tenant.repositories",
    "core.modules.tenant.service",
    "core.modules.tenant.slug.policy",
    "core.modules.tenant.helpers",
    # Kernel-level shared integration helpers
    "core.kernel.app.app_container",
    "core.kernel.runtime.clock",
    "core.kernel.config",
    "core.kernel.http.app_errors",
    "core.kernel.http.app_dependencies",
    "core.kernel.http.responses",
    "core.kernel.http.security_errors",
    "core.kernel.interface.keys",
    "core.kernel.interface.app_keys",
    "core.kernel.interface.app_conventions",
    "core.kernel.interface.observability",
    "core.kernel.audit",
    "core.infrastructure.audit.const",
    "core.infrastructure.audit.service",
    "core.kernel.process",
    "core.kernel.jobs",
    "core.kernel.deps.facade",
    "core.kernel.http.tenant_dependencies",
    "core.kernel.db.model_bases",
    "core.kernel.security.csrf_middleware",
    "core.kernel.security.security_headers_middleware",
    "core.kernel.security.cookie_policy",
    "core.kernel.security.rate_limit",
)

PUBLIC_SHARED_APPS_PREFIXES: tuple[str, ...] = (
    "apps.state_keys",
)

APP_PLATFORM_SUPPORT_DIRECTORIES: tuple[str, ...] = ()

__all__ = [
    "APP_PLATFORM_SUPPORT_DIRECTORIES",
    "PUBLIC_CORE_API_PREFIXES",
    "PUBLIC_SHARED_APPS_PREFIXES",
]
