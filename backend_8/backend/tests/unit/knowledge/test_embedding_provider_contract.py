from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, *, model: str, input):  # type: ignore[no-untyped-def]
        self.calls.append({"model": model, "input": input})
        if isinstance(input, list):
            data = [SimpleNamespace(embedding=[float(idx), float(idx) + 0.5]) for idx, _ in enumerate(input, start=1)]
            return SimpleNamespace(data=data)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.25, 0.75])])


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsClient()


def _import_embedding_service_class():
    openai_module = types.ModuleType("openai")
    openai_module.AsyncOpenAI = object
    sys.modules["openai"] = openai_module
    module = importlib.import_module("apps.knowledge.ai.embedding_service")
    return module.EmbeddingService


def _build_service():
    service_cls = _import_embedding_service_class()
    service = object.__new__(service_cls)
    service._client = _FakeOpenAIClient()
    service._model = "contract-model"
    return service


@pytest.mark.anyio
async def test_embed_text_uses_configured_model_and_returns_vector() -> None:
    service = _build_service()

    vector = await service.embed_text("AIPLAZA pilot knowledge content")

    assert vector == [0.25, 0.75]
    assert service._client.embeddings.calls == [
        {"model": "contract-model", "input": "AIPLAZA pilot knowledge content"}
    ]


@pytest.mark.anyio
async def test_embed_texts_returns_vectors_for_all_inputs_in_order() -> None:
    service = _build_service()

    vectors = await service.embed_texts(["alpha", "beta", "gamma"])

    assert vectors == [[1.0, 1.5], [2.0, 2.5], [3.0, 3.5]]
    assert service._client.embeddings.calls == [
        {"model": "contract-model", "input": ["alpha", "beta", "gamma"]}
    ]


@pytest.mark.anyio
async def test_embed_texts_normalizes_none_to_empty_strings() -> None:
    service = _build_service()

    await service.embed_texts(["first", "", None])  # type: ignore[list-item]

    assert service._client.embeddings.calls[0]["input"] == ["first", "", ""]
