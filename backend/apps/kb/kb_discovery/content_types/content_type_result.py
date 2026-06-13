from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentTypeCandidate:
    content_type: str
    confidence: float
    detector: str
    signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContentTypeResult:
    content_type: str
    confidence: float
    candidates: tuple[ContentTypeCandidate, ...] = ()
    detectors: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = ["ContentTypeCandidate", "ContentTypeResult"]
