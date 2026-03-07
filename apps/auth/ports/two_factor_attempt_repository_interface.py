# apps/auth/ports/two_factor_attempt_repository_interface.py
# INTERFÉSZ – 2FA sikertelen próbálkozások (brute-force védelem).
# 2026.03 - Sárközi Mihály

from abc import ABC, abstractmethod


class TwoFactorAttemptRepositoryInterface(ABC):
    """Interface: 2FA próbálkozás számlálók (pending token / user / IP)."""

    @abstractmethod
    def is_blocked(self, scope: str, scope_key: str, max_attempts: int, window_minutes: int) -> bool:
        """True ha a scope/key már elérte a max_attempts-et az ablakban (új login step1 kell)."""
        ...

    @abstractmethod
    def record_failed(self, scope: str, scope_key: str, window_minutes: int) -> int:
        """Sikertelen próbálkozás rögzítése; vissza az aktuális attempts számot."""
        ...

    @abstractmethod
    def reset_for_success(self, pending_token_key: str, user_id: int, ip: str | None) -> None:
        """Sikeres 2FA után mindhárom scope törlése (token, user, ip)."""
        ...
