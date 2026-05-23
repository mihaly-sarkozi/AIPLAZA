# backend/core/modules/auth/use_cases/__init__.py
# Feladat: Az auth use case osztályok lazy exportfelülete. LoginService, LogoutService, RefreshService és TwoFactorService importját késlelteti, hogy a modul assembly és router importok ne töltsenek be felesleges függőségeket. Auth application/use case csomagbelépő.
# Sárközi Mihály - 2026.05.21


def __getattr__(name: str):
    if name == "LoginService":
        from core.modules.auth.use_cases.login_service import LoginService

        return LoginService
    if name == "LogoutService":
        from core.modules.auth.use_cases.logout_service import LogoutService

        return LogoutService
    if name == "RefreshService":
        from core.modules.auth.use_cases.refresh_service import RefreshService

        return RefreshService
    if name == "TwoFactorService":
        from core.modules.auth.use_cases.two_factor_service import TwoFactorService

        return TwoFactorService
    raise AttributeError(name)

__all__ = [
    "LoginService",
    "LogoutService",
    "RefreshService",
    "TwoFactorService",
]
