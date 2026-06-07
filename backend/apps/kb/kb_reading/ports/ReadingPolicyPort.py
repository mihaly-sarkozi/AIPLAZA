from __future__ import annotations

# backend/apps/kb/kb_reading/ports/ReadingPolicyPort.py
# Feladat: Szabályzat lekérdezés a beolvasáshoz.
# Sárközi Mihály - 2026.06.07

from typing import Protocol


class ReadingPolicyPort(Protocol):
    """Szerződés szabályzat lekérdezéshez."""
    """Ellenőrzi a betanítási kvótát."""
    def check_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        ...

    """Rögzíti a betanítási felhasználást."""
    def record_training_usage(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None: ...

    """Szükség esetén kéri a többfaktoros hitelesítést."""
    def require_training_mfa_if_needed(self, user: object) -> None:
        ...


__all__ = ["ReadingPolicyPort"]
