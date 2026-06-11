from __future__ import annotations

# backend/apps/kb/kb_crud/domain/CrudErrorCode.py
# Feladat: Tudástár CRUD nyelvfüggetlen hibakódok.
# Sárközi Mihály - 2026.06.07

from enum import Enum


class CrudErrorCode(str, Enum):
    KB_NOT_FOUND = "kb_not_found"
    KB_NAME_EXISTS = "kb_name_exists"
    KB_NAME_INVALID = "kb_name_invalid"
    KB_CONFIRM_NAME_MISMATCH = "kb_confirm_name_mismatch"
    KB_LIMIT_REACHED = "kb_limit_reached"
    KB_DELETE_NOT_ALLOWED = "kb_delete_not_allowed"
    PERMISSION_DENIED = "kb_permission_denied"
    TOO_MANY_KB_IDS = "kb_too_many_ids"


__all__ = ["CrudErrorCode"]
