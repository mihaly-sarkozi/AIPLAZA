# backend/core/modules/auth/domain/two_factor_policy.py
# Feladat: A 2FA próbálkozási limit, időablak és kódlejárat közös policy helperjeit adja. Settingsből olvas, de default értékekkel is működik, hogy a TwoFactorService konzisztens brute-force védelmet kapjon. Auth domain policy a kétfaktoros belépési folyamathoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Optional


def get_2fa_max_attempts() -> int:
    """Max sikertelen 2FA kód próbálkozás (pending_token / user / IP) ablakon belül."""
    try:
        from core.kernel.config.config_loader import settings
        return int(getattr(settings, "two_fa_max_attempts", 5))
    except (ImportError, TypeError, ValueError):
        return 5


def get_2fa_attempt_window_minutes() -> int:
    """Ablak (perc), amelyen belül a max_attempts számít (utána nullázódik)."""
    try:
        from core.kernel.config.config_loader import settings
        return int(getattr(settings, "two_fa_attempt_window_minutes", 15))
    except (ImportError, TypeError, ValueError):
        return 15


def get_2fa_code_expiry_minutes() -> int:
    """2FA kód érvényessége percekben (emailben küldött kód)."""
    try:
        from core.kernel.config.config_loader import settings
        return int(getattr(settings, "two_fa_code_expiry_minutes", 10))
    except (ImportError, TypeError, ValueError):
        return 10
