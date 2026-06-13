from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscoveryChecklist:
    has_entities: bool = False
    has_chunks: bool = False
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def core_complete(self) -> bool:
        return self.has_chunks


class ValidateDiscoveryResult:
    def __call__(
        self,
        *,
        chunk_count: int,
        entity_count: int,
    ) -> DiscoveryChecklist:
        checks = {
            "chunks": chunk_count > 0,
            "entities": entity_count >= 0,
        }
        missing = tuple(name for name, passed in checks.items() if not passed and name != "entities")
        return DiscoveryChecklist(
            has_entities=entity_count > 0,
            has_chunks=checks["chunks"],
            missing=missing,
        )


__all__ = ["DiscoveryChecklist", "ValidateDiscoveryResult"]
