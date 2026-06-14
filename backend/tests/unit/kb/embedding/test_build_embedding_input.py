from __future__ import annotations

from apps.kb.kb_embedding.dto.EmbeddingChunkDto import EmbeddingChunkDto
from apps.kb.kb_embedding.dto.EmbeddingDiscoveryBundleDto import EmbeddingDiscoveryBundleDto
from apps.kb.kb_embedding.service.BuildEmbeddingInputService import BuildEmbeddingInputService


def test_build_embedding_input_is_deterministic():
    service = BuildEmbeddingInputService()
    chunk = EmbeddingChunkDto(
        chunk_id="chunk_1",
        text="A szerződést HubSpotban kell rögzíteni.",
        chunk_type="process",
        order_index=0,
        section_title="Szerződéskezelés",
    )
    bundle = EmbeddingDiscoveryBundleDto(
        chunk_id="chunk_1",
        language_code="hu",
        content_type="process",
        heading_path="Onboarding / Szerződéskezelés",
        keywords=("szerződés", "HubSpot"),
        topics=("document_management", "sales"),
        entities=("HubSpot", "Zalka 2000 Kft."),
    )
    first = service.build(chunk, bundle, title="Onboarding")
    second = service.build(chunk, bundle, title="Onboarding")
    assert first.input_hash == second.input_hash
    assert "Cím: Onboarding / Szerződéskezelés" in first.input_text
    assert "Kulcsszavak: szerződés, HubSpot" in first.input_text


def test_build_embedding_input_excludes_unselected_metadata():
    service = BuildEmbeddingInputService()
    chunk = EmbeddingChunkDto(
        chunk_id="chunk_2",
        text="Teszt szöveg",
        chunk_type="text",
        order_index=1,
        page_number=42,
        metadata={"source_part_ids": ["part_1"], "score_detail": 0.99},
    )
    built = service.build(chunk, None, title="Doc")
    assert "page" not in built.input_text.lower()
    assert "part_1" not in built.input_text
    assert "0.99" not in built.input_text
