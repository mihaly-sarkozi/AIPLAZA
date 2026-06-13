from __future__ import annotations

from typing import Any, Callable, Protocol

from apps.kb.shared.contracts import DiscoveryChunkSnapshot


class ChunkReaderPort(Protocol):
    def list_for_document(self, document_id: str) -> list[DiscoveryChunkSnapshot]: ...


class UnderstandingJobReaderPort(Protocol):
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...


__all__ = ["ChunkReaderPort", "UnderstandingJobReaderPort"]
