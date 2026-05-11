from __future__ import annotations

import types

import pytest

from apps.knowledge.ai.embedding_provider import LocalBgeM3EmbeddingProvider, build_embedding_provider_from_settings

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_local_bge_provider_batches_and_returns_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeModel:
        def __init__(self, _key: str) -> None:
            self.calls: list[list[str]] = []

        def encode(self, batch, **_kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(list(batch))
            return [[float(index), float(index) + 0.5] for index, _ in enumerate(batch, start=1)]

    provider = LocalBgeM3EmbeddingProvider(model_key="BAAI/bge-m3", vector_size=1024, batch_size=2)
    monkeypatch.setattr(
        "apps.knowledge.ai.embedding_provider.LocalBgeM3EmbeddingProvider._load_model",
        classmethod(lambda cls, _model_key: _FakeModel(_model_key)),
    )

    vectors = await provider.embed_texts(["első", "második", "harmadik"])

    assert len(vectors) == 3
    assert vectors[0] == [1.0, 1.5]
    assert vectors[2] == [1.0, 1.5]


def test_build_embedding_provider_from_settings_defaults_to_local() -> None:
    settings = types.SimpleNamespace(
        embedding_provider="local",
        embedding_model="BAAI/bge-m3",
        embedding_vector_size=1024,
        embedding_batch_size=16,
        openai_api_key="",
    )
    provider = build_embedding_provider_from_settings(settings)
    assert provider.model_key == "BAAI/bge-m3"
    assert provider.vector_size == 1024
