from __future__ import annotations


class PersonDisambiguator:
    def is_ambiguous(self, alias: str, alias_map: dict[str, str]) -> bool:
        canonicals = {alias_map[key] for key in alias_map if key == alias}
        return len(canonicals) > 1


__all__ = ["PersonDisambiguator"]
