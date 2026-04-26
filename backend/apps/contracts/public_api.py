from __future__ import annotations

"""Machine-readable app platform import boundaries."""

PUBLIC_CORE_API_PREFIXES: tuple[str, ...] = (
    # Stable platform contracts
    "core.platform.contract",
    "core.platform.contract.observability",
    "core.platform.extensions.tenant_hooks",
    "core.platform.service_keys",
    "core.platform.settings.models",
    "core.platform.settings.repositories",
    "core.platform.settings.sections",
    "core.platform.settings.services",
    "core.platform.settings.tenant_hooks",
    "core.platform.auth.auth_dependencies",
    # Shared capability contracts used by apps
    "core.capabilities.users.dto",
    "core.capabilities.users.models.user_orm",
    "core.capabilities.users.repositories.user_repository",
    # Tenant integration surfaces
    "core.extensions.tenant.models.tenant_orm",
    "core.extensions.tenant.repositories",
    "core.extensions.tenant.service",
    "core.extensions.tenant.slug.policy",
    # Kernel-level shared integration helpers
    "core.di",
    "core.kernel.bootstrap.container",
    "core.kernel.clock",
    "core.kernel.config",
    "core.kernel.db.model_bases",
    "core.kernel.middleware.security",
    "core.kernel.security.cookie_policy",
    "core.kernel.security.rate_limit",
)

PUBLIC_SHARED_APPS_PREFIXES: tuple[str, ...] = (
    "apps.contracts",
    "apps.di",
    "apps.state_keys",
)

APP_PLATFORM_SUPPORT_DIRECTORIES: tuple[str, ...] = (
    "_template",
    "contracts",
)

__all__ = [
    "APP_PLATFORM_SUPPORT_DIRECTORIES",
    "PUBLIC_CORE_API_PREFIXES",
    "PUBLIC_SHARED_APPS_PREFIXES",
]
