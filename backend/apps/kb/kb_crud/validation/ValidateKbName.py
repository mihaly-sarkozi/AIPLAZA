from __future__ import annotations

# backend/apps/kb/kb_crud/validation/ValidateKbName.py
# Feladat: Tudástár név normalizálása és validálása.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError

KB_NAME_MAX_LENGTH = 200


class ValidateKbName:
    """Név normalizálás (trim) és hossz/üresség ellenőrzés."""

    @staticmethod
    def execute(raw_name: str | None) -> str:
        name = (raw_name or "").strip()
        if not name or len(name) > KB_NAME_MAX_LENGTH:
            raise CrudValidationError(CrudErrorCode.KB_NAME_INVALID)
        return name


__all__ = ["KB_NAME_MAX_LENGTH", "ValidateKbName"]
