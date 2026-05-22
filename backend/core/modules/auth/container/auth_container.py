# backend/core/modules/auth/container/auth_container.py
# Feladat: Az auth modul runtime feature bundle-jét definiálja. A login, refresh, logout és two-factor service példányokat egy immutable containerbe fogja össze, hogy a ModuleContext state-ben továbbadhatók legyenek. Auth assembly helper, nem saját DI framework.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass

from core.modules.auth.use_cases.login_service import LoginService
from core.modules.auth.use_cases.logout_service import LogoutService
from core.modules.auth.use_cases.refresh_service import RefreshService
from core.modules.auth.use_cases.two_factor_service import TwoFactorService


@dataclass(frozen=True)
class AuthFeatureContainer:
    # Felhasználó bejelentkezés üzleti logikája
    login_service: LoginService
    # Authentikációhoz szükséges frissitő kulcs előállítása
    refresh_service: RefreshService
    # Kilépés üzleti logikája
    logout_service: LogoutService
    # Kétfaktoros azonosítás használatának üzleti logikája
    two_factor_service: TwoFactorService


# Ez a függvény felépíti a(z) auth feature logikáját.
def build_auth_feature(
    *,
    login_service: LoginService,
    refresh_service: RefreshService,
    logout_service: LogoutService,
    two_factor_service: TwoFactorService,
) -> AuthFeatureContainer:
    return AuthFeatureContainer(
        login_service=login_service,
        refresh_service=refresh_service,
        logout_service=logout_service,
        two_factor_service=two_factor_service,
    )
