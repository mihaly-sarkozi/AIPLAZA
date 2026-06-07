from __future__ import annotations


class KbError(Exception):
    pass


class KbNotFoundError(KbError):
    pass


class KbValidationError(KbError):
    pass


class KbPermissionError(KbError):
    pass


class KbProcessingError(KbError):
    pass


__all__ = [
    "KbError",
    "KbNotFoundError",
    "KbPermissionError",
    "KbProcessingError",
    "KbValidationError",
]
