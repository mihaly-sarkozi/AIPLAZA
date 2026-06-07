from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedUrlResponse:
    body: bytes
    status_code: int
    final_url: str
    content_type: str | None
    headers: dict[str, str]


__all__ = ["FetchedUrlResponse"]
