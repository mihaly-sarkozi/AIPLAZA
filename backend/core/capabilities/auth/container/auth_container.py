# A auth modul DI container-je.
# 2026.04.03 - Sárközi Mihály

from __future__ import annotations

from dataclasses import dataclass

from core.capabilities.auth.service.login_service import LoginService
from core.capabilities.auth.service.logout_service import LogoutService
from core.capabilities.auth.service.refresh_service import RefreshService
from core.capabilities.auth.service.two_factor_service import TwoFactorService


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
