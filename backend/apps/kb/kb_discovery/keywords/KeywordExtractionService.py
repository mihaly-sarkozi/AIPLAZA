from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeKeywordDto
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.keywords.PhraseExtractor import PhraseExtractor
from apps.kb.kb_discovery.keywords.StopwordProvider import StopwordProvider
from apps.kb.kb_discovery.keywords.TermFrequencyExtractor import TermFrequencyExtractor
from apps.kb.kb_discovery.keywords.KeywordRanker import KeywordRanker
from apps.kb.kb_discovery.mapper.discovery_mapper import keyword_dto_to_orm
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository


class KeywordExtractionService:
    def __init__(self, keyword_repository: KeywordRepository) -> None:
        self._keyword_repository = keyword_repository
        self._stopwords = StopwordProvider()
        self._tf = TermFrequencyExtractor(self._stopwords)
        self._phrases = PhraseExtractor(self._stopwords)
        self._ranker = KeywordRanker()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> list[KnowledgeKeywordDto]:
        keywords: list[KnowledgeKeywordDto] = []
        for chunk in chunks:
            terms = self._tf.extract(chunk.text)
            phrases = self._phrases.extract(chunk.text)
            ranked = self._ranker.rank(terms + phrases)
            for rank, (term, score) in enumerate(ranked[:20], start=1):
                keywords.append(
                    KnowledgeKeywordDto(chunk_id=chunk.chunk_id, term=term, rank=rank, score=score)
                )
        self._keyword_repository.replace_for_job(
            ctx.job_id, [keyword_dto_to_orm(ctx, keyword) for keyword in keywords]
        )
        return keywords


__all__ = ["KeywordExtractionService"]
