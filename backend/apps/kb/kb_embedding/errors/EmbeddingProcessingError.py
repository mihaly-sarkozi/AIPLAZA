from __future__ import annotations


class EmbeddingProcessingError(Exception):
    def __init__(self, code: str, *, retryable: bool = False, **details) -> None:
        self.code = code
        self.retryable = retryable
        self.details = details
        super().__init__(code)


__all__ = ["EmbeddingProcessingError"]
