"""Tenant platform modul – signup, lifecycle policy, extension wiring.

A tenant signup platform-szinten csak a szükséges platform service-eket ismeri.
Az app-oldali tenant extension hookok külön platform registry-n keresztül
csatlakoznak.
"""
from __future__ import annotations

from core.platform.composition import AppModule, ModuleContext
from core.extensions.tenant.container.tenant_container import build_tenant_extension
from core.platform.extensions.tenant_hooks import get_tenant_extension_registry
from core.platform.tenant_policy import TenantLifecyclePolicy
from core.platform.service_keys import PLATFORM_CLOCK_SERVICE, PLATFORM_TENANT_EXTENSION_REGISTRY_SERVICE, PLATFORM_TENANT_LIFECYCLE_POLICY, PLATFORM_TENANT_SIGNUP_FACTORY, PLATFORM_USERS_SERVICE


class TenantPlatformModule(AppModule):
    key = "platform.tenant"

    def service_dependencies(self) -> tuple[str, ...]:
        """Kötelező platform service-ek (Phase 1-ben regisztrálódnak)."""
        return (PLATFORM_USERS_SERVICE, PLATFORM_CLOCK_SERVICE)

    def register(self, container: ModuleContext) -> None:
        user_service = container.get_service(PLATFORM_USERS_SERVICE)
        lifecycle_policy = TenantLifecyclePolicy()
        tenant_extension_registry = get_tenant_extension_registry()
        container.register_service(PLATFORM_TENANT_EXTENSION_REGISTRY_SERVICE, tenant_extension_registry)
        container.register_service(PLATFORM_TENANT_LIFECYCLE_POLICY, lifecycle_policy)

        feature = build_tenant_extension(
            tenant_repo=container.infrastructure.repositories.tenant_repo,
            user_service=user_service,
            db_engine=container.infrastructure.db_session_factory.engine,
            lifecycle_policy=lifecycle_policy,
            clock=container.get_service(PLATFORM_CLOCK_SERVICE),
            token_service=container.security.token_service,
            audit_service=container.audit_service,
            tenant_extension_registry=tenant_extension_registry,
        )
        builder = lambda request_base_url_builder: feature.build_tenant_signup_service(
            request_base_url_builder,
        )
        container.register_factory(PLATFORM_TENANT_SIGNUP_FACTORY, builder)

    def permissions(self) -> tuple[str, ...]:
        return ("tenant.signup", "tenant.read")


def get_module() -> AppModule:
    return TenantPlatformModule()
