# backend/core/kernel/observability/sinks.py
# Feladat: Opcionális külső observability sink szerződéseket tartalmaz. Az ObservabilityEvent és ExceptionSink segítségével Sentryhez vagy más exception tracking adapterhez lehet stabil interfészt adni, a NoopExceptionSink pedig alapértelmezett üres implementáció. Core extension point, jelenleg lightweight integrációs felület.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ObservabilityEvent:
    name: str
    fields: dict[str, Any] = field(default_factory=dict)


class ExceptionSink(Protocol):
    """Exception fókuszú külső sink, például Sentry adapter számára."""

    def capture_exception(self, error: BaseException, event: ObservabilityEvent) -> None:
        ...


class NoopExceptionSink:
    def capture_exception(self, error: BaseException, event: ObservabilityEvent) -> None:
        return None


__all__ = ["ExceptionSink", "NoopExceptionSink", "ObservabilityEvent"]
