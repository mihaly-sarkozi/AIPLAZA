from __future__ import annotations

from typing import Protocol

from apps.kb.kb_reading.ports.FetchedUrlResponse import FetchedUrlResponse


class ReadingSecurityPort(Protocol):
    def fetch_url(self, url: str, *, timeout: float | None = None) -> FetchedUrlResponse: ...


__all__ = ["ReadingSecurityPort"]
