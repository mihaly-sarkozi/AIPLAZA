from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits
from apps.kb.kb_understanding.extract.ocr_engine import OcrExtractStats
from apps.kb.kb_understanding.extract.part_counters import PartCounters


@dataclass
class ExtractContext:
    streaming: bool = False
    limits: ExtractLimits | None = None
    counters: PartCounters = field(default_factory=PartCounters)
    ocr_stats: OcrExtractStats = field(default_factory=OcrExtractStats)
    on_parts_batch: Callable[[list[ExtractPart]], None] | None = None
    on_progress: Callable[[dict], None] | None = None
    pending_parts: list[ExtractPart] = field(default_factory=list)

    def emit_parts(self, parts: list[ExtractPart], *, batch_size: int) -> None:
        if not parts:
            return
        self.counters.add_parts(parts)
        if self.streaming and self.on_parts_batch is not None:
            self.pending_parts.extend(parts)
            while len(self.pending_parts) >= batch_size:
                chunk = self.pending_parts[:batch_size]
                del self.pending_parts[:batch_size]
                self.on_parts_batch(chunk)
        else:
            self.pending_parts.extend(parts)

    def flush(self) -> None:
        if self.streaming and self.pending_parts and self.on_parts_batch is not None:
            chunk = list(self.pending_parts)
            self.pending_parts.clear()
            self.on_parts_batch(chunk)


__all__ = ["ExtractContext"]
