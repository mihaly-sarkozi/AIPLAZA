from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class KnowledgeFacadeRuntime:
    attributes: Mapping[str, Any]

    @classmethod
    def from_owner(cls, owner: Any) -> "KnowledgeFacadeRuntime":
        return cls(attributes=dict(owner.__dict__))

    def bind_to(self, owner: Any) -> None:
        owner.__dict__.update(self.attributes)


__all__ = ["KnowledgeFacadeRuntime"]
