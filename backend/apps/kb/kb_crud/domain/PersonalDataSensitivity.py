from __future__ import annotations

# backend/apps/kb/kb_crud/domain/PersonalDataSensitivity.py
# Feladat: Tudástár személyes adat érzékenységi szint enum.
# Sárközi Mihály - 2026.06.11

from enum import Enum


class PersonalDataSensitivity(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


__all__ = ["PersonalDataSensitivity"]
