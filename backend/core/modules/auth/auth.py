# backend/core/modules/auth/auth.py
# Feladat: Az auth platform modult regisztráló BaseAppModule implementáció. Felépíti a login, refresh, logout és 2FA service-eket, publikálja őket platform service kulcsokon, regisztrálja a tenant schema hookokat és deklarálja az auth permissionöket. Core module assembly, nem HTTP route vagy üzleti algoritmus részlet.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.auth.container.auth_container import build_auth_feature
from core.modules.auth.use_cases import LoginService, LogoutService, RefreshService, TwoFactorService
from core.modules.auth.tenant_hooks import register_auth_tenant_hooks
from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.state_keys import CTX_STATE_AUTH_FEATURE
from core.kernel.interface.keys import (
    PLATFORM_AUTH_SESSION_REPOSITORY,
    PLATFORM_AUTH_TWO_FACTOR_SERVICE,
    PLATFORM_CLOCK_SERVICE,
    PLATFORM_LOGIN_SERVICE,
    PLATFORM_LOGOUT_SERVICE,
    PLATFORM_REFRESH_SERVICE,
    PLATFORM_SETTINGS_SERVICE,
)
from core.modules.auth.domain.two_factor_policy import (
    get_2fa_attempt_window_minutes,
    get_2fa_code_expiry_minutes,
    get_2fa_max_attempts,
)


class AuthCoreModule(BaseAppModule):
    key = "platform.auth"

    def service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_SETTINGS_SERVICE, PLATFORM_CLOCK_SERVICE)

    # Ez a metódus regisztrálja a(z) register logikáját.
    def register(self, container: ModuleContext) -> None:
        repos = container.infrastructure.repositories
        settings_service = container.get_service(PLATFORM_SETTINGS_SERVICE)
        clock = container.get_service(PLATFORM_CLOCK_SERVICE)

        two_factor_service = TwoFactorService(
            repos.two_factor_repo,
            container.infrastructure.email_service,
            attempt_repo=repos.two_factor_attempt_repo,
            max_attempts=get_2fa_max_attempts(),
            attempt_window_minutes=get_2fa_attempt_window_minutes(),
            code_expiry_minutes=get_2fa_code_expiry_minutes(),
            event_channel=container.security.event_channel,
            clock=clock,
        )
        login_service = LoginService(
            repos.user_repo,
            repos.session_repo,
            repos.pending_2fa_repo,
            container.security.token_service,
            container.security.security_logger,
            two_factor_service,
            container.security.audit_service,
            two_factor_settings=settings_service,
            user_authenticator_repository=repos.user_authenticator_repo,
            transaction_manager=container.infrastructure.db_session_factory.transaction,
            clock=clock,
        )
        refresh_service = RefreshService(
            repos.session_repo,
            container.security.token_service,
            container.security.security_logger,
            container.security.audit_service,
            user_repository=repos.user_repo,
            transaction_manager=container.infrastructure.db_session_factory.transaction,
        )
        logout_service = LogoutService(
            repos.session_repo,
            container.security.token_service,
            container.security.security_logger,
            container.security.audit_service,
            transaction_manager=container.infrastructure.db_session_factory.transaction,
        )
        feature = build_auth_feature(
            login_service=login_service,
            refresh_service=refresh_service,
            logout_service=logout_service,
            two_factor_service=two_factor_service,
        )
        container.set_state(CTX_STATE_AUTH_FEATURE, feature)
        container.register_repository(PLATFORM_AUTH_SESSION_REPOSITORY, repos.session_repo)
        container.register_service(PLATFORM_AUTH_TWO_FACTOR_SERVICE, two_factor_service)
        container.register_service(PLATFORM_LOGIN_SERVICE, login_service)
        container.register_service(PLATFORM_REFRESH_SERVICE, refresh_service)
        container.register_service(PLATFORM_LOGOUT_SERVICE, logout_service)

    # Ez a metódus a(z) tenant_schema_hooks logikáját valósítja meg.
    def tenant_schema_hooks(self) -> tuple:
        return (register_auth_tenant_hooks,)

    # Ez a metódus a(z) permissions logikáját valósítja meg.
    def permissions(self) -> tuple[str, ...]:
        return ("auth.login", "auth.refresh", "auth.logout")

