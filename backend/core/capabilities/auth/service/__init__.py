# Ez a fájl a(z) core/capabilities/auth/service csomag exportjait és inicializálási pontjait fogja össze.


def __getattr__(name: str):
    if name == "LoginService":
        from core.capabilities.auth.service.login_service import LoginService

        return LoginService
    if name == "LogoutService":
        from core.capabilities.auth.service.logout_service import LogoutService

        return LogoutService
    if name == "RefreshService":
        from core.capabilities.auth.service.refresh_service import RefreshService

        return RefreshService
    if name == "TwoFactorService":
        from core.capabilities.auth.service.two_factor_service import TwoFactorService

        return TwoFactorService
    raise AttributeError(name)

__all__ = [
    "LoginService",
    "LogoutService",
    "RefreshService",
    "TwoFactorService",
]
