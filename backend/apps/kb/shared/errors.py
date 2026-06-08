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


class KbStorageError(KbError):
    """Nyers anyag tárolási hiba (pl. érvénytelen storage kulcs szegmens)."""

    def __init__(self, code: str, **params: object) -> None:
        self.code = code
        self.params = params
        super().__init__(code)


__all__ = [
    "KbError",
    "KbNotFoundError",
    "KbPermissionError",
    "KbProcessingError",
    "KbStorageError",
    "KbValidationError",
]
