from __future__ import annotations

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.entities.legal_form_company_parser import (
    collect_company_name_before_suffix,
    suffix_match_is_valid,
)
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.gazetteers.LegalFormGazetteer import LegalFormGazetteer


class LegalFormCompanyRecognizer(BaseRecognizer):
    name = "legal_form_company"
    version = "2.0"

    def __init__(
        self,
        gazetteer: LegalFormGazetteer | None = None,
        *,
        max_company_name_tokens: int = 4,
    ) -> None:
        self._gazetteer = gazetteer or LegalFormGazetteer()
        self._normalizer = TextNormalizer()
        self._max_company_name_tokens = max_company_name_tokens

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        known_names = self._known_names(context)
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            pattern = self._gazetteer.suffix_pattern_for_language(chunk.language_code)
            raw_matches = [
                suffix_match
                for suffix_match in pattern.finditer(chunk.text)
                if suffix_match_is_valid(chunk.text, suffix_match.start(), suffix_match.end())
            ]
            for suffix_match in self._longest_non_overlapping(raw_matches):
                parsed = collect_company_name_before_suffix(
                    chunk.text,
                    suffix_match.start(),
                    suffix_match.end(),
                    language_code=chunk.language_code,
                    legal_form=self._gazetteer.resolve_legal_form(
                        suffix_match.group(0), chunk.language_code
                    ),
                    matched_suffix=suffix_match.group(0),
                    max_tokens=self._max_company_name_tokens,
                    known_names=known_names,
                )
                if parsed is None or len(parsed.name) < 3:
                    continue
                full_name = self._gazetteer.lookup_full_name_for_suffix(
                    parsed.matched_suffix, chunk.language_code
                )
                metadata: list[tuple[str, object]] = [
                    ("recognizer", self.name),
                    ("legal_form", parsed.legal_form),
                    ("legal_form_source", "suffix"),
                    ("matched_suffix", parsed.matched_suffix),
                    ("company_name_tokens", list(parsed.company_name_tokens)),
                ]
                if parsed.boundary_stop:
                    metadata.append(("boundary_stop", parsed.boundary_stop))
                if full_name:
                    metadata.extend(
                        (
                            ("legal_form_dataset", "GLEIF_ELF"),
                            ("legal_form_full_name", full_name),
                        )
                    )
                candidates.append(
                    EntityCandidate(
                        entity_type=EntityType.COMPANY,
                        name=parsed.name,
                        normalized_name=self._normalizer.normalize(parsed.name),
                        chunk_id=chunk.chunk_id,
                        start_offset=parsed.start_offset,
                        end_offset=parsed.end_offset,
                        confidence=0.93,
                        source=self.name,
                        language_code=chunk.language_code,
                        subtype="legal_entity",
                        metadata=tuple(metadata),
                    )
                )
        return candidates

    @staticmethod
    def _known_names(context: DiscoveryContext) -> frozenset[str]:
        names: set[str] = set()
        for entry in context.entity_dictionary or ():
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                if name:
                    names.add(name)
                for alias in entry.get("aliases") or ():
                    alias_text = str(alias).strip()
                    if alias_text:
                        names.add(alias_text)
        return frozenset(names)

    @staticmethod
    def _longest_non_overlapping(matches: list[object]) -> list[object]:
        ordered = sorted(
            matches,
            key=lambda match: (match.start(), -(match.end() - match.start())),
        )
        kept: list[object] = []
        for match in ordered:
            start, end = match.start(), match.end()
            if any(not (end <= other.start() or start >= other.end()) for other in kept):
                continue
            kept.append(match)
        return sorted(kept, key=lambda match: match.start())


__all__ = ["LegalFormCompanyRecognizer"]
