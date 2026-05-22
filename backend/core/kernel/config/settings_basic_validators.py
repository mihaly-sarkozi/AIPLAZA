# backend/core/kernel/config/settings_basic_validators.py
# Feladat: Az alap settings mezők egyszerű konzisztencia-validációit tartalmazza. Ide tartozik a jelszó policy szint, cookie SameSite/Secure kapcsolat, token TTL értékek és 2FA időablakok ellenőrzése. A base.py a settings_validators facade-on keresztül hívja, ezért belső config validációs helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from core.kernel.config.settings_constants import (
    ALLOWED_COOKIE_SAMESITE_VALUES,
    ALLOWED_PASSWORD_SECURITY_LEVELS,
)


def validate_password_policy_level(settings: Any) -> None:
    level = (settings.password_security_level or "").strip().lower()
    if level not in ALLOWED_PASSWORD_SECURITY_LEVELS:
        raise ValueError(
            f"password_security_level érvénytelen: {level!r}. "
            "Megengedett értékek: basic, standard, high."
        )


def validate_cookie_samesite(settings: Any) -> None:
    samesite = (settings.cookie_samesite or "").strip().lower()
    if samesite not in ALLOWED_COOKIE_SAMESITE_VALUES:
        raise ValueError(
            f"cookie_samesite érvénytelen érték: {samesite!r}. "
            "Megengedett értékek: lax, strict, none."
        )
    if samesite == "none" and settings.cookie_secure is False:
        raise ValueError(
            "cookie_samesite='none' csak cookie_secure=True esetén érvényes "
            "(a böngésző különben elutasítja a cookie-t)."
        )


def validate_ttl(settings: Any) -> None:
    if settings.access_ttl_min <= 0:
        raise ValueError(f"access_ttl_min értéke {settings.access_ttl_min}, de pozitívnak kell lennie.")
    if settings.refresh_ttl_days <= 0:
        raise ValueError(f"refresh_ttl_days értéke {settings.refresh_ttl_days}, de pozitívnak kell lennie.")
    if settings.refresh_ttl_session_hours <= 0:
        raise ValueError(
            f"refresh_ttl_session_hours értéke {settings.refresh_ttl_session_hours}, de pozitívnak kell lennie."
        )
    refresh_in_min = settings.refresh_ttl_days * 24 * 60
    if settings.access_ttl_min >= refresh_in_min:
        raise ValueError(
            f"access_ttl_min ({settings.access_ttl_min} perc) >= refresh_ttl_days "
            f"({settings.refresh_ttl_days} nap = {refresh_in_min} perc). "
            "Az access token élettartama rövidebb kell legyen a refresh tokenénél."
        )


def validate_2fa(settings: Any) -> None:
    if settings.two_fa_max_attempts <= 0:
        raise ValueError(f"two_fa_max_attempts pozitívnak kell lennie, kapott: {settings.two_fa_max_attempts}.")
    if settings.two_fa_attempt_window_minutes <= 0:
        raise ValueError(
            f"two_fa_attempt_window_minutes pozitívnak kell lennie, kapott: {settings.two_fa_attempt_window_minutes}."
        )
    if settings.two_fa_code_expiry_minutes <= 0:
        raise ValueError(
            f"two_fa_code_expiry_minutes pozitívnak kell lennie, kapott: {settings.two_fa_code_expiry_minutes}."
        )
    if settings.two_fa_code_expiry_minutes >= settings.two_fa_attempt_window_minutes:
        raise ValueError(
            f"two_fa_code_expiry_minutes ({settings.two_fa_code_expiry_minutes}) "
            f">= two_fa_attempt_window_minutes ({settings.two_fa_attempt_window_minutes}). "
            "A 2FA kód lejárata rövidebb kell legyen a kísérlet ablaknál."
        )


__all__ = [
    "validate_2fa",
    "validate_cookie_samesite",
    "validate_password_policy_level",
    "validate_ttl",
]
