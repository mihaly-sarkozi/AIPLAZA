from __future__ import annotations


class SearchNotReadyError(Exception):
    def __init__(
        self,
        message: str = "A kiválasztott tudástár még nem kereshető.",
        *,
        blocked_reasons: tuple[str, ...] = (),
        status: str = "BLOCKED_NOT_READY",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.blocked_reasons = blocked_reasons
        self.status = status


__all__ = ["SearchNotReadyError"]
