from __future__ import annotations

# backend/apps/kb/kb_crud/domain/PersonalDataMode.py
# Feladat: Tudástár személyes adat kezelési mód enum.
# Sárközi Mihály - 2026.06.11

from enum import Enum


class PersonalDataMode(str, Enum):
    NO_PERSONAL_DATA = "no_personal_data"
    WITH_CONFIRMATION = "with_confirmation"
    ALLOWED_NOT_TO_AI = "allowed_not_to_ai"
    NO_PII_FILTER = "no_pii_filter"


__all__ = ["PersonalDataMode"]
