# backend/core/modules/users/users.py
# Feladat: A users platform modult regisztráló BaseAppModule implementáció. A UsersFeatureContaineren keresztül összerakja a user, profile és invite service-eket, service kulcsokon publikálja őket, valamint tenant schema hookokat regisztrál. Core platform module assembly a felhasználókezeléshez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.infrastructure.audit.tenant_hooks import register_audit_tenant_hooks
from core.modules.users.container.users_container import build_users_feature
from core.modules.users.tenant_hooks import register_users_tenant_hooks
from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.state_keys import CTX_STATE_USERS_FEATURE
from core.kernel.interface.keys import (
    PLATFORM_USERS_INVITE_SERVICE,
    PLATFORM_USERS_PROFILE_SERVICE,
    PLATFORM_USERS_SERVICE,
)


class UsersCoreModule(BaseAppModule):
    key = "platform.users"

    # Ez a metódus regisztrálja a(z) register logikáját.
    def register(self, container: ModuleContext) -> None:
        repos = container.infrastructure.repositories
        feature = build_users_feature(
            user_repo=repos.user_repo,
            invite_token_repo=repos.invite_token_repo,
            audit_service=container.security.audit_service,
            session_repo=repos.session_repo,
            email_service=container.security.email_service,
            transaction_manager=container.infrastructure.db_session_factory.transaction,
        )
        container.set_state(CTX_STATE_USERS_FEATURE, feature)
        container.register_service(PLATFORM_USERS_SERVICE, feature.service)
        container.register_service(PLATFORM_USERS_PROFILE_SERVICE, feature.profile_service)
        container.register_service(PLATFORM_USERS_INVITE_SERVICE, feature.invite_service)

    # Ez a metódus a(z) tenant_schema_hooks logikáját valósítja meg.
    def tenant_schema_hooks(self) -> tuple:
        return (register_users_tenant_hooks, register_audit_tenant_hooks)

    # Ez a metódus a(z) permissions logikáját valósítja meg.
    def permissions(self) -> tuple[str, ...]:
        return (
            "users.read",
            "users.write",
            "users.invite",
        )

