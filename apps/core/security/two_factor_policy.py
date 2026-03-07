# apps/core/security/two_factor_policy.py
# Központi 2FA policy: retry limit, ablak, kód lejárat. Config-ból vagy default.
# A TwoFactorService ezt használja; egy helyen lehet finomhangolni (lock, ablak).
# Biztonság: brute-force védelem konzisztens; architektúra: egy réteg.

from __future__ import annotations

from typing import Optional


def get_2fa_max_attempts() -> int:
    """Max sikertelen 2FA kód próbálkozás (pending_token / user / IP) ablakon belül."""
    try:
        from config.settings import settings
        return int(getattr(settings, "two_fa_max_attempts", 5))
    except Exception:
        return 5


def get_2fa_attempt_window_minutes() -> int:
    """Ablak (perc), amelyen belül a max_attempts számít (utána nullázódik)."""
    try:
        from config.settings import settings
        return int(getattr(settings, "two_fa_attempt_window_minutes", 15))
    except Exception:
        return 15


def get_2fa_code_expiry_minutes() -> int:
    """2FA kód érvényessége percekben (emailben küldött kód)."""
    try:
        from config.settings import settings
        return int(getattr(settings, "two_fa_code_expiry_minutes", 10))
    except Exception:
        return 10
