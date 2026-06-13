from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.enrichment.LocalKnowledgeEnrichmentService import LocalKnowledgeEnrichmentService
from apps.kb.kb_discovery.entities.ExtractEntitiesService import ExtractEntitiesService
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.service.LanguageDetectionService import LanguageDetectionService

pytestmark = pytest.mark.unit


class _FakeJobRepo:
    def __init__(self) -> None:
        self.metadata: dict = {}

    def update_metadata(self, job_id: str, patch: dict) -> None:
        self.metadata.update(patch)


class _FakeEntityRepo:
    def replace_for_document(self, *args, **kwargs):
        pass

    def count_for_document(self, *args, **kwargs):
        return 0


class _FakeMentionRepo:
    def replace_for_job(self, *args, **kwargs):
        pass

    def list_by_job_grouped_by_chunk(self, *args, **kwargs):
        return {}


class _FakeEnrichmentRepo:
    def __init__(self) -> None:
        self.rows = []

    def replace_for_job(self, job_id, rows):
        self.rows = rows


class _FakeKeywordRepo:
    def __init__(self) -> None:
        self.rows = []

    def replace_for_job(self, job_id, rows):
        self.rows = rows


class _FakeTopicRepo:
    def __init__(self) -> None:
        self.rows = []

    def replace_for_job(self, job_id, rows):
        self.rows = rows


def _ctx(language_code="unknown", language_confidence=0.0):
    return DiscoveryJobContext(
        job_id="disc_job_1",
        understanding_job_id="und_job_1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id="kb1",
        tenant_slug="tenant",
        created_by=1,
        source_type="text",
        title="Misi okos",
        language_code=language_code,
        language_confidence=language_confidence,
    )


def test_misi_okos_without_person_directory_has_zero_entities():
    service = ExtractEntitiesService(_FakeEntityRepo(), _FakeMentionRepo(), person_directory=[])
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Misi okos",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    entities, mentions = service.run(_ctx(), chunks)
    assert len(entities) == 0


def test_misi_okos_enrichment_extracts_keywords():
    keyword_repo = _FakeKeywordRepo()
    service = LocalKnowledgeEnrichmentService(
        _FakeEnrichmentRepo(),
        keyword_repo,
        _FakeTopicRepo(),
        _FakeMentionRepo(),
    )
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Misi okos",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    result = service.run(_ctx(language_code="hu", language_confidence=0.6), chunks)
    assert len(result.enrichments) == 1
    assert result.enrichments[0].metadata["keyword_count"] >= 1
    assert len(keyword_repo.rows) >= 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Az ügyfél számlázása Budapesten történik.", SupportedLanguage.HU),
        ("The customer onboarding starts in London.", SupportedLanguage.EN),
        ("La factura se crea en Madrid.", SupportedLanguage.ES),
    ],
)
def test_language_detection_hu_en_es(text, expected):
    repo = _FakeJobRepo()
    service = LanguageDetectionService(repo)
    chunks = [DiscoveryChunkDto(chunk_id="c1", text=text, chunk_type="paragraph", order_index=0)]
    result = service.run(_ctx(), chunks)
    assert result.language_code == expected.value
    assert result.language_confidence > 0


def test_multilingual_enrichment_topics_by_language():
    service = LocalKnowledgeEnrichmentService(
        _FakeEnrichmentRepo(),
        _FakeKeywordRepo(),
        _FakeTopicRepo(),
        _FakeMentionRepo(),
    )
    cases = [
        ("Az ügyfél számlázása Budapesten történik.", "hu", "billing"),
        ("The customer onboarding starts in London.", "en", "customer_onboarding"),
        ("La factura se crea en Madrid.", "es", "billing"),
    ]
    for text, language_code, expected_topic in cases:
        chunks = [
            DiscoveryChunkDto(
                chunk_id="c1",
                text=text,
                chunk_type="paragraph",
                order_index=0,
                language_code=language_code,
            )
        ]
        result = service.run(_ctx(language_code=language_code, language_confidence=0.8), chunks)
        assert expected_topic in result.enrichments[0].metadata.get("top_topics", [])
