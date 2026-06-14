from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeleteIndexedChunksResult:
    requested: int = 0
    qdrant_deleted: int = 0
    postgres_updated: int = 0
    failed_point_ids: tuple[str, ...] = field(default_factory=tuple)
    error_code: str | None = None

    @property
    def partial(self) -> bool:
        return bool(self.failed_point_ids) or bool(self.error_code)


__all__ = ["DeleteIndexedChunksResult"]
