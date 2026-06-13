from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonAliasEntry:
    raw_alias: str
    normalized_alias: str
    canonical_name: str


__all__ = ["PersonAliasEntry"]
