from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QdrantPayloadDto:
    payload: dict[str, Any] = field(default_factory=dict)
    payload_hash: str = ""


__all__ = ["QdrantPayloadDto"]
