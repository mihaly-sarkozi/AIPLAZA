from __future__ import annotations

import re

from apps.kb.kb_discovery.common.AccentPatternBuilder import accent_insensitive_pattern
from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.persons.PersonAliasEntry import PersonAliasEntry
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import PersonConfidenceScorer
from apps.kb.kb_discovery.persons.PersonDisambiguator import PersonDisambiguator


class PersonAliasRecognizer(BaseRecognizer):
    name = "person_alias"
    version = "1.2"

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()
        self._person_scorer = PersonConfidenceScorer()
        self._disambiguator = PersonDisambiguator()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        entries = self._build_alias_entries(context.person_directory)
        if not entries:
            return []

        patterns: list[tuple[re.Pattern[str], PersonAliasEntry]] = [
            (accent_insensitive_pattern(entry.raw_alias), entry) for entry in entries
        ]
        ambiguous_aliases = self._disambiguator.ambiguous_normalized_aliases(entries)

        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for pattern, entry in patterns:
                for match in pattern.finditer(chunk.text):
                    candidates.append(
                        EntityCandidate(
                            entity_type=EntityType.PERSON,
                            name=match.group(0),
                            normalized_name=self._normalizer.normalize(entry.canonical_name),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=self._person_scorer.score(
                                directory_hit=True,
                                ambiguous=entry.normalized_alias in ambiguous_aliases,
                            ),
                            aliases=(entry.raw_alias,),
                            source=self.name,
                            subtype="directory_alias",
                        )
                    )
        return candidates

    def _build_alias_entries(self, directory: list[dict]) -> list[PersonAliasEntry]:
        entries: list[PersonAliasEntry] = []
        seen: set[tuple[str, str, str]] = set()
        for entry in directory:
            canonical = str(entry.get("name") or "").strip()
            if not canonical:
                continue
            aliases = [canonical] + [
                str(alias).strip() for alias in (entry.get("aliases") or []) if str(alias).strip()
            ]
            for raw_alias in aliases:
                normalized_alias = self._normalizer.normalize(raw_alias)
                if not normalized_alias:
                    continue
                key = (raw_alias.casefold(), normalized_alias, canonical.casefold())
                if key in seen:
                    continue
                seen.add(key)
                entries.append(
                    PersonAliasEntry(
                        raw_alias=raw_alias,
                        normalized_alias=normalized_alias,
                        canonical_name=canonical,
                    )
                )
        return entries


__all__ = ["PersonAliasRecognizer"]
