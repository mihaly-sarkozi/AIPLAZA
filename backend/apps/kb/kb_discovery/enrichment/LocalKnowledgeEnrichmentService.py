from __future__ import annotations

import re
from collections import Counter

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.content_types.FaqDetector import FaqDetector
from apps.kb.kb_discovery.content_types.ProcessDetector import ProcessDetector
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.languages.language_profiles import keyword_hints_for, stopwords_for, topic_rules_for
from apps.kb.kb_discovery.mapper.discovery_mapper import keyword_dto_to_orm, topic_dto_to_orm
from apps.kb.kb_discovery.mapper.enrichment_mapper import enrichment_dto_to_orm
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeKeywordDto, KnowledgeTopicDto
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository


class LocalKnowledgeEnrichmentService:
    _TOKEN = re.compile(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+", re.UNICODE)
    _SENTENCE = re.compile(r"[^.!?]+[.!?]?")

    def __init__(
        self,
        enrichment_repository: EnrichmentRepository,
        keyword_repository: KeywordRepository,
        topic_repository: TopicRepository,
    ) -> None:
        self._enrichment_repository = enrichment_repository
        self._keyword_repository = keyword_repository
        self._topic_repository = topic_repository
        self._normalizer = TextNormalizer()
        self._faq = FaqDetector()
        self._process = ProcessDetector()

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
    ) -> list[KnowledgeEnrichmentDto]:
        language = SupportedLanguage(ctx.language_code) if ctx.language_code in SupportedLanguage._value2member_map_ else SupportedLanguage.UNKNOWN
        stopwords = stopwords_for(language)
        topic_rules = topic_rules_for(language)
        hints = keyword_hints_for(language)

        enrichments: list[KnowledgeEnrichmentDto] = []
        keywords: list[KnowledgeKeywordDto] = []
        topics: list[KnowledgeTopicDto] = []

        for chunk in chunks:
            lead = self._lead_sentence(chunk.text)
            terms = self._extract_keywords(chunk.text, stopwords, hints)
            matched_topics = self._match_topics(chunk.text, topic_rules)
            content_type = self._detect_content_type(chunk)
            confidence = self._confidence(terms, matched_topics, ctx.language_confidence)

            enrichment = KnowledgeEnrichmentDto(
                chunk_id=chunk.chunk_id,
                lead_sentence=lead,
                keywords=tuple(terms),
                topics=tuple(matched_topics),
                content_type=content_type,
                language_code=ctx.language_code,
                language_confidence=ctx.language_confidence,
                possible_questions=(),
                confidence=confidence,
            )
            enrichments.append(enrichment)

            for rank, term in enumerate(terms[:20], start=1):
                keywords.append(
                    KnowledgeKeywordDto(chunk_id=chunk.chunk_id, term=term, rank=rank, score=1.0 / rank)
                )
            for topic_key in matched_topics:
                topics.append(
                    KnowledgeTopicDto(chunk_id=chunk.chunk_id, topic_key=topic_key, confidence=0.7)
                )

        self._enrichment_repository.replace_for_job(
            ctx.job_id, [enrichment_dto_to_orm(ctx, dto) for dto in enrichments]
        )
        self._keyword_repository.replace_for_job(
            ctx.job_id, [keyword_dto_to_orm(ctx, keyword) for keyword in keywords]
        )
        self._topic_repository.replace_for_job(
            ctx.job_id, [topic_dto_to_orm(ctx, topic) for topic in topics]
        )
        return enrichments

    def _lead_sentence(self, text: str) -> str:
        match = self._SENTENCE.search(text.strip())
        return (match.group(0).strip() if match else text.strip())[:500]

    def _extract_keywords(self, text: str, stopwords: frozenset[str], hints: frozenset[str]) -> list[str]:
        counter: Counter[str] = Counter()
        for match in self._TOKEN.finditer(text):
            token = self._normalizer.normalize_token(match.group(0))
            if len(token) < 2 or token in stopwords:
                continue
            counter[token] += 1
        ranked = [term for term, _ in counter.most_common()]
        for hint in hints:
            if hint in text.lower() and hint not in ranked:
                ranked.insert(0, hint)
        return ranked[:20]

    def _match_topics(self, text: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
        lowered = text.lower()
        matched: list[str] = []
        for topic_key, markers in rules.items():
            if any(marker in lowered for marker in markers):
                matched.append(topic_key)
        return matched

    def _detect_content_type(self, chunk: DiscoveryChunkDto) -> str:
        if self._faq.detect(chunk.text):
            return "faq"
        if self._process.detect(chunk.text):
            return "process"
        if chunk.chunk_type in {"table", "list", "step"}:
            return chunk.chunk_type
        return "note"

    def _confidence(self, keywords: list[str], topics: list[str], language_confidence: float) -> float:
        base = 0.3 + min(0.4, len(keywords) * 0.05) + min(0.2, len(topics) * 0.1)
        return round(min(1.0, base + language_confidence * 0.1), 4)


__all__ = ["LocalKnowledgeEnrichmentService"]
