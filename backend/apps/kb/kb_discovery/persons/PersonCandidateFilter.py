from __future__ import annotations

from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate


class PersonCandidateFilter:
    """Longest-match / priority filter person candidate-ekre mention zaj csökkentésére."""

    _FULL_NAME_SOURCES = frozenset({"full_person_name"})
    _ALIAS_SOURCES = frozenset({"person_alias"})
    _GIVEN_NAME_SOURCES = frozenset({"given_name"})

    def filter(self, candidates: list[EntityCandidate]) -> list[EntityCandidate]:
        by_chunk: dict[str, list[EntityCandidate]] = {}
        for candidate in candidates:
            by_chunk.setdefault(candidate.chunk_id, []).append(candidate)

        filtered: list[EntityCandidate] = []
        for chunk_candidates in by_chunk.values():
            filtered.extend(self._filter_chunk(chunk_candidates))
        return filtered

    def _filter_chunk(self, candidates: list[EntityCandidate]) -> list[EntityCandidate]:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                self._priority(candidate),
                candidate.end_offset - candidate.start_offset,
                candidate.confidence,
            ),
            reverse=True,
        )
        kept: list[EntityCandidate] = []
        for candidate in ordered:
            if any(self._overlaps(candidate, other) for other in kept):
                continue
            kept.append(candidate)
        return sorted(kept, key=lambda candidate: candidate.start_offset)

    def _priority(self, candidate: EntityCandidate) -> int:
        if candidate.source in self._FULL_NAME_SOURCES or candidate.subtype == "full_name":
            return 4
        if candidate.source in self._ALIAS_SOURCES:
            if len(candidate.name.split()) >= 2:
                return 3
            return 1
        if candidate.source in self._GIVEN_NAME_SOURCES or candidate.subtype == "given_name":
            return 0
        return 2

    @staticmethod
    def _overlaps(left: EntityCandidate, right: EntityCandidate) -> bool:
        return not (left.end_offset <= right.start_offset or left.start_offset >= right.end_offset)


__all__ = ["PersonCandidateFilter"]
