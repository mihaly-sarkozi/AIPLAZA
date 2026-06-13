from __future__ import annotations

from apps.kb.kb_discovery.persons.PersonAliasEntry import PersonAliasEntry


class PersonDisambiguator:
    def ambiguous_normalized_aliases(self, entries: list[PersonAliasEntry]) -> frozenset[str]:
        canonicals_by_alias: dict[str, set[str]] = {}
        for entry in entries:
            canonicals_by_alias.setdefault(entry.normalized_alias, set()).add(
                entry.canonical_name.casefold()
            )
        return frozenset(
            alias for alias, canonicals in canonicals_by_alias.items() if len(canonicals) > 1
        )

    def is_ambiguous(self, alias: str, alias_map: dict[str, str]) -> bool:
        canonicals = {alias_map[key] for key in alias_map if key == alias}
        return len(canonicals) > 1


__all__ = ["PersonDisambiguator"]
