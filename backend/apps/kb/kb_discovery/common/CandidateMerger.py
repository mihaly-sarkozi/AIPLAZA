from __future__ import annotations

from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate


class CandidateMerger:
    def merge(self, candidates: list[EntityCandidate]) -> list[EntityCandidate]:
        merged: dict[tuple[str, str, str], EntityCandidate] = {}
        for candidate in candidates:
            key = (candidate.entity_type.value, candidate.normalized_name, candidate.chunk_id)
            existing = merged.get(key)
            if existing is None or candidate.confidence > existing.confidence:
                merged[key] = candidate
        return list(merged.values())


__all__ = ["CandidateMerger"]
