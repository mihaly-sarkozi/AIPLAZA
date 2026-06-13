from __future__ import annotations


class DiscoveryNotFoundError(Exception):
    def __init__(self, code: str, **details) -> None:
        self.code = code
        self.details = details
        super().__init__(code)


__all__ = ["DiscoveryNotFoundError"]
