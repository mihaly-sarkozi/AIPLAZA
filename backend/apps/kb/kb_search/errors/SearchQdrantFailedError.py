from __future__ import annotations


class SearchQdrantFailedError(Exception):
    def __init__(self, message: str = "A vektor keresés jelenleg nem elérhető.") -> None:
        super().__init__(message)
        self.message = message


__all__ = ["SearchQdrantFailedError"]
