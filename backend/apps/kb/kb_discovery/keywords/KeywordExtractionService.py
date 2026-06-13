from __future__ import annotations

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeKeywordDto
from apps.kb.kb_discovery.enrichment.chunk_metadata_boost import chunk_metadata_boost, heading_terms
from apps.kb.kb_discovery.enrichment.entity_signals import keyword_boosts_from_entities
from apps.kb.kb_discovery.keywords.KeywordDictionaryProvider import KeywordDictionaryProvider
from apps.kb.kb_discovery.keywords.PhraseExtractor import KeywordRanker, PhraseExtractor
from apps.kb.kb_discovery.keywords.TermFrequencyExtractor import StopwordProvider, TermFrequencyExtractor
from apps.kb.kb_discovery.orm.EntityMention import EntityMention

EXTRACTOR_VERSION = "2.0"
_MAX_KEYWORDS = 25


class KeywordExtractionService:
    def __init__(self) -> None:
        self._stopwords = StopwordProvider()
        self._tf = TermFrequencyExtractor(self._stopwords)
        self._phrases = PhraseExtractor(self._stopwords)
        self._ranker = KeywordRanker()
        self._dictionary = KeywordDictionaryProvider()
        self._normalizer = TextNormalizer()

    def extract_for_chunk(
        self,
        chunk: DiscoveryChunkDto,
        *,
        language_code: str,
        mentions: list[EntityMention] | None = None,
    ) -> list[KnowledgeKeywordDto]:
        items: list[tuple[str, float, dict[str, object]]] = []
        items.extend(self._tf.extract(chunk.text, language_code=language_code))
        items.extend(self._phrases.extract(chunk.text, language_code=language_code))
        items.extend(keyword_boosts_from_entities(mentions or []))

        dictionary = self._dictionary.entries_for(language_code)
        lowered_text = chunk.text.casefold()
        for entry in dictionary.values():
            for candidate in (entry.phrase, *entry.aliases):
                if candidate.casefold() in lowered_text:
                    items.append(
                        (
                            entry.phrase,
                            0.6 * entry.weight,
                            {
                                "source": "dictionary_hint",
                                "matched_dictionary": f"keywords_{language_code}.json",
                                "category": entry.category,
                            },
                        )
                    )
                    break

        for heading in heading_terms(chunk):
            items.append(
                (
                    heading,
                    0.7,
                    {
                        "source": "heading_derived",
                        "from_heading": True,
                    },
                )
            )

        metadata_boost = chunk_metadata_boost(chunk)
        ranked = self._ranker.rank(items)
        keywords: list[KnowledgeKeywordDto] = []
        for rank, (term, score, metadata) in enumerate(ranked[:_MAX_KEYWORDS], start=1):
            adjusted_score = round(min(1.0, score + metadata_boost), 4)
            normalized = self._normalizer.normalize(term)
            keywords.append(
                KnowledgeKeywordDto(
                    chunk_id=chunk.chunk_id,
                    term=term[:256],
                    normalized_term=normalized[:256],
                    display_term=term[:256],
                    language_code=language_code,
                    rank=rank,
                    score=adjusted_score,
                    confidence=adjusted_score,
                    source=str(metadata.get("source") or "term_frequency"),
                    extractor_version=EXTRACTOR_VERSION,
                    start_offset=_optional_int(metadata.get("start_offset")),
                    end_offset=_optional_int(metadata.get("end_offset")),
                    metadata={
                        key: value
                        for key, value in metadata.items()
                        if key not in {"start_offset", "end_offset"}
                    },
                )
            )
        return keywords


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


__all__ = ["EXTRACTOR_VERSION", "KeywordExtractionService"]
