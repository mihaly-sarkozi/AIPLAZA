# backend/core/modules/users/domain/policies/login_security_policy.py
# Feladat: Login security policyt tartalmaz user lockout és sikertelen belépési számláló kezeléshez. User DTO állapotból dönt lockout, reset és failure increment viselkedésről. Auth-érzékeny users domain policy.
# Sárközi Mihály - 2026.05.21

"""Bejelentkezési biztonsági politika.

Felelősség: meghatározza, hogy hány egymást követő sikertelen bejelentkezési
kísérlet után kell zárolni egy felhasználói fiókot, és hogy owner fiókokra
vonatkozik-e a zárolás.

A döntési logika NEM a repository, hanem ez az osztály felelőssége.
A UserRepository.record_failed_login meghívja ezt a politikát, és csak az
eredmény alapján végzi el az adatbázis-módosítást.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.modules.users.domain.dto.user import User

FAILED_LOGIN_LOCKOUT_THRESHOLD: int = 5
"""Sikertelen bejelentkezések száma, amely után a (nem-owner) fiók zárolódik."""


@dataclass(frozen=True)
class FailedLoginDecision:
    """A sikertelen bejelentkezés kiértékelésének eredménye."""

    new_failed_attempts: int
    """Az új értéke a failed_login_attempts számlálónak DB-ben."""
    should_lock_account: bool
    """Ha True, a fiókot inaktívra kell állítani."""


class LoginSecurityPolicy:
    """Sikertelen bejelentkezések kezelési politikája.

    Szabályok:
    - Owner felhasználók soha nem kerülnek zárolásra.
    - ``lockout_threshold`` egymást követő sikertelen kísérlet után
      (nem-owner) fiók inaktívvá válik, és a számláló nullázódik.
    """

    def __init__(self, lockout_threshold: int = FAILED_LOGIN_LOCKOUT_THRESHOLD) -> None:
        if lockout_threshold < 1:
            raise ValueError("lockout_threshold legalább 1 kell legyen")
        self._threshold = lockout_threshold

    def evaluate_failed_login(self, user: User) -> FailedLoginDecision:
        """Meghatározza a sikertelen bejelentkezés következményét.

        Args:
            user: Az aktuális domain User (tartalmaznia kell a failed_login_attempts
                  és is_owner mezőket).

        Returns:
            FailedLoginDecision – tartalmazza az új számláló-értéket és hogy
            zárolni kell-e a fiókot.
        """
        current_count = getattr(user, "failed_login_attempts", 0)
        new_count = current_count + 1
        should_lock = new_count >= self._threshold and not user.is_owner
        return FailedLoginDecision(
            new_failed_attempts=0 if should_lock else new_count,
            should_lock_account=should_lock,
        )
