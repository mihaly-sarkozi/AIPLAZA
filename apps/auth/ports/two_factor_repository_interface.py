# apps/auth/ports/two_factor_repository_interface.py
# INTERFÉSZ – A 2FA kódokat reprezentálja
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.auth.domain.two_factor_code import TwoFactorCode


class TwoFactorRepositoryInterface(ABC):
    """Interface: 2FA kódok lekérése/mentése. Implementáció: infrastructure réteg."""
    @abstractmethod
    def create(self, code: "TwoFactorCode") -> "TwoFactorCode":
        """Új 2FA kód létrehozása."""
        ...

    @abstractmethod
    def get_valid_code(self, user_id: int, code: str) -> Optional["TwoFactorCode"]:
        """Érvényes, nem használt kód lekérése."""
        ...

    @abstractmethod
    def invalidate_user_codes(self, user_id: int) -> None:
        """Felhasználó összes kódjának érvénytelenítése."""
        ...

    @abstractmethod
    def mark_as_used(self, code_id: int) -> None:
        """Kód használatának jelölése."""
        ...
