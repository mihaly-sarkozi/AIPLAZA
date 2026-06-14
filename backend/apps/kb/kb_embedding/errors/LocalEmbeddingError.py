from __future__ import annotations


class LocalEmbeddingError(Exception):
    """Helyi sentence-transformers adapter domain hiba."""

    def __init__(self, code: str, *, message: str | None = None, **details) -> None:
        self.code = code
        self.message = message or code
        self.details = details
        super().__init__(self.message)


__all__ = ["LocalEmbeddingError"]
