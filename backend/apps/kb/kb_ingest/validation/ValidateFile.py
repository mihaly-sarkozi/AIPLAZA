from __future__ import annotations

# backend/apps/kb/kb_ingest/validation/ValidateFile.py
# Feladat: Fájl metaadat és tartalom ellenőrzés.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

import os

from apps.kb.kb_ingest.config.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.shared.errors import KbValidationError


def extension_from_filename(filename: str) -> str:
    """Kiterjesztést nyer ki a fájlnévből."""
    name = str(filename or "").strip().lower()
    if "." not in name:
        return ""
    return f".{name.rsplit('.', 1)[1]}"


def validate_file_name(filename: str | None) -> str:
    """A modul egyik műveletét hajtja végre."""
    name = str(filename or "").strip()
    if not name:
        raise KbValidationError("File name is required")
    if len(name) > 255:
        raise KbValidationError("File name is too long")
    if any(ch in name for ch in ("\x00", "/", "\\")):
        raise KbValidationError("Invalid file name")
    if name in {".", ".."} or name.endswith(".."):
        raise KbValidationError("Invalid file name")
    base_name = os.path.basename(name)
    if base_name != name:
        raise KbValidationError("Invalid file name")
    return base_name


def validate_extension(
    filename: str,
    *,
    config: ReadingConfig | None = None,
) -> str:
    """A modul egyik műveletét hajtja végre."""
    cfg = config or DEFAULT_READING_CONFIG
    validated_name = validate_file_name(filename)
    extension = extension_from_filename(validated_name)
    if extension not in cfg.allowed_extensions:
        allowed = ", ".join(sorted(cfg.allowed_extensions))
        raise KbValidationError(f"Unsupported file extension. Allowed: {allowed}")
    return extension


def validate_size(size_bytes: int, *, max_bytes: int | None = None, config: ReadingConfig | None = None) -> None:
    """A modul egyik műveletét hajtja végre."""
    cfg = config or DEFAULT_READING_CONFIG
    limit = max_bytes if max_bytes is not None else cfg.max_file_bytes
    if size_bytes < 0:
        raise KbValidationError("Invalid file size")
    if size_bytes > limit:
        raise KbValidationError(f"File too large (max {limit // (1024 * 1024)} MB)")


__all__ = ["extension_from_filename", "validate_extension", "validate_file_name", "validate_size"]
