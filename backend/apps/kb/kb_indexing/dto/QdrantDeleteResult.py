from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QdrantDeleteResult:
    requested: int = 0
    deleted: int = 0
    missing: int = 0
    failed_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def partial(self) -> bool:
        return bool(self.failed_ids) or (self.requested > 0 and self.deleted + self.missing < self.requested)


__all__ = ["QdrantDeleteResult"]
