from __future__ import annotations

from enum import Enum


class CrudErrorCode(str, Enum):
    KB_NOT_FOUND = "kb_not_found"
    KB_NAME_EXISTS = "kb_name_exists"


__all__ = ["CrudErrorCode"]
