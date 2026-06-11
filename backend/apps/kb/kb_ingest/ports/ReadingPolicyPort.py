from __future__ import annotations

# backend/apps/kb/kb_ingest/ports/ReadingPolicyPort.py
# Feladat: Szabályzat lekérdezés a tanítási feltöltéshez (kvóta, MFA).
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

from typing import Protocol


class ReadingPolicyPort(Protocol):
    """Szerződés szabályzat lekérdezéshez."""

    def check_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        ...

    def record_training_usage(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None: ...

    def require_training_mfa_if_needed(self, user: object) -> None:
        ...


__all__ = ["ReadingPolicyPort"]
