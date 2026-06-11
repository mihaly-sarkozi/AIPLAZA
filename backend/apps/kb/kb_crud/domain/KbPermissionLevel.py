from __future__ import annotations

# backend/apps/kb/kb_crud/domain/KbPermissionLevel.py
# Feladat: Tudástár felhasználói jogosultsági szint enum (use/train/none).
# Sárközi Mihály - 2026.06.11

from enum import Enum


class KbPermissionLevel(str, Enum):
    USE = "use"
    TRAIN = "train"
    NONE = "none"

    @classmethod
    def stored_values(cls) -> set[str]:
        """A DB-ben eltárolható értékek (a ``none`` nem kerül tárolásra)."""
        return {cls.USE.value, cls.TRAIN.value}


__all__ = ["KbPermissionLevel"]
